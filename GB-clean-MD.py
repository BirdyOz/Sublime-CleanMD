import os
import re
import shutil
import subprocess

import sublime
import sublime_plugin
from bs4 import BeautifulSoup

DEFAULT_CLEANMD_CONFIG = {
    "promote_word_paragraph_breaks": True,
    "normalize_html_fragments": True,
    "add_safe_external_link_attrs": True,
    "run_formatter_after_clean": True,
    "open_preview_after_clean": True,
    "html_block_tags": ["figure", "div"],
    "html_prettier": {
        "print_width": 800,
        "tab_width": 4,
        "html_whitespace_sensitivity": "css",
        "prose_wrap": "preserve",
        "embedded_language_formatting": "auto",
    },
}

def load_cleanmd_settings():
    return sublime.load_settings("CleanMD.sublime-settings")

def build_cleanmd_config(overrides=None, settings_obj=None):
    settings = settings_obj or load_cleanmd_settings()
    config = {
        "promote_word_paragraph_breaks": settings.get(
            "promote_word_paragraph_breaks",
            DEFAULT_CLEANMD_CONFIG["promote_word_paragraph_breaks"],
        ),
        "normalize_html_fragments": settings.get(
            "normalize_html_fragments",
            DEFAULT_CLEANMD_CONFIG["normalize_html_fragments"],
        ),
        "add_safe_external_link_attrs": settings.get(
            "add_safe_external_link_attrs",
            DEFAULT_CLEANMD_CONFIG["add_safe_external_link_attrs"],
        ),
        "run_formatter_after_clean": settings.get(
            "run_formatter_after_clean",
            DEFAULT_CLEANMD_CONFIG["run_formatter_after_clean"],
        ),
        "open_preview_after_clean": settings.get(
            "open_preview_after_clean",
            DEFAULT_CLEANMD_CONFIG["open_preview_after_clean"],
        ),
        "html_block_tags": settings.get(
            "html_block_tags",
            list(DEFAULT_CLEANMD_CONFIG["html_block_tags"]),
        ),
        "html_prettier": dict(DEFAULT_CLEANMD_CONFIG["html_prettier"]),
    }

    html_prettier = settings.get("html_prettier", {})
    if isinstance(html_prettier, dict):
        config["html_prettier"].update(html_prettier)

    if isinstance(overrides, dict):
        for key, value in overrides.items():
            if key == "html_prettier" and isinstance(value, dict):
                config["html_prettier"].update(value)
            else:
                config[key] = value

    return config

def get_cleanmd_config():
    return build_cleanmd_config()


class CleanMd(sublime_plugin.TextCommand):

    def run(self, edit, side_effects=True):

        file_name = self.view.file_name() or ""

        if ".docx" in file_name:
            dir_name = os.path.dirname(file_name)
            assets_dir = dir_name.replace(" ","\\ ") + "/assets"
            file_name = file_name.replace(" ","\\ ")
            md_name = file_name.replace(".docx", ".md")
            pandoc = "pandoc -f docx -t gfm " + file_name + " -o " + md_name + " --extract-media=" + assets_dir + " --wrap=none --columns=8000 --tab-stop=4"
            os.system(pandoc)
            window = self.view.window()
            if window is not None:
                window.open_file(md_name.replace("\\ "," "))

        else:
            overrides = None if side_effects else {
                "run_formatter_after_clean": False,
                "open_preview_after_clean": False,
            }
            replacestrings(self, edit, config_overrides=overrides)

def normalize_html_fragments(string, config=None):
    """Safely normalize img and anchor tags without reparsing the whole document."""
    if "<" not in string or ">" not in string:
        return string, {"img_tags_normalized": 0, "external_links_hardened": 0}
    if config is None:
        config = DEFAULT_CLEANMD_CONFIG
    stats = {"img_tags_normalized": 0, "external_links_hardened": 0}

    def normalize_img_tag(match):
        nonlocal stats
        tag_markup = match.group(0)
        soup = BeautifulSoup(tag_markup, "html.parser")
        tag = soup.find("img")
        if tag is None:
            return tag_markup

        style = tag.get("style")
        if isinstance(style, str) and style:
            rules = []
            for rule in style.split(";"):
                rule = rule.strip()
                if not rule:
                    continue
                if rule.lower().startswith("width:"):
                    continue
                rules.append(rule)

            if rules:
                tag["style"] = "; ".join(rules)
            else:
                del tag["style"]
            stats["img_tags_normalized"] += 1

        return str(tag)

    def normalize_anchor_open_tag(match):
        nonlocal stats
        open_tag = match.group(0)
        soup = BeautifulSoup(open_tag + "</a>", "html.parser")
        tag = soup.find("a")
        if tag is None:
            return open_tag

        href = tag.get("href", "")
        if not isinstance(href, str):
            href = ""
        if tag.has_attr("target"):
            del tag["target"]
        if tag.has_attr("rel"):
            del tag["rel"]
        if re.match(r"^https?://", href, flags=re.IGNORECASE):
            tag["target"] = "_blank"
            tag["rel"] = "noopener noreferrer"
            stats["external_links_hardened"] += 1

        serialised = str(tag)
        if serialised.endswith("</a>"):
            return serialised[:-4]
        return open_tag

    string = re.sub(r"<img\b[^>]*?>", normalize_img_tag, string, flags=re.IGNORECASE | re.DOTALL)
    if config.get("add_safe_external_link_attrs", True):
        string = re.sub(r"<a\b[^>]*?>", normalize_anchor_open_tag, string, flags=re.IGNORECASE | re.DOTALL)
    return string, stats

def find_top_level_html_blocks(string, tag_names=("figure", "div")):
    """Return source ranges for top-level figure/div blocks that begin a line."""
    tag_pattern = "|".join(re.escape(tag) for tag in tag_names)
    opener = re.compile(r'(?m)^[ \t]*<({})\b[^>]*?>'.format(tag_pattern), flags=re.IGNORECASE)
    tag_re = re.compile(r'<(/?)({})\b[^>]*?>'.format(tag_pattern), flags=re.IGNORECASE | re.DOTALL)

    blocks = []
    position = 0
    while True:
        match = opener.search(string, position)
        if not match:
            break

        start = match.start()
        depth = 0
        end = None
        for tag_match in tag_re.finditer(string, start):
            is_closing = tag_match.group(1) == "/"
            markup = tag_match.group(0)
            is_self_closing = markup.rstrip().endswith("/>")

            if not is_closing:
                if not is_self_closing:
                    depth += 1
            else:
                depth -= 1
                if depth == 0:
                    end = tag_match.end()
                    break

        if end is None:
            position = match.end()
            continue

        while end < len(string) and string[end] in "\t ":
            end += 1
        if end < len(string) and string[end] == "\n":
            end += 1

        blocks.append({
            "start": start,
            "end": end,
            "tag": match.group(1).lower(),
        })
        position = end

    return blocks

def apply_base_indentation(text, indent):
    """Indent formatted fragment lines to match the block's original base indent."""
    if not indent:
        return text

    lines = text.splitlines()
    return "\n".join((indent + line) if line else line for line in lines)

def repair_nested_paragraph_wrappers(fragment):
    """Unwrap invalid outer <p> tags that contain only nested block <p> tags."""
    soup = BeautifulSoup(fragment, "html.parser")

    changed = True
    while changed:
        changed = False
        for p_tag in soup.find_all("p"):
            child_tags = [child for child in p_tag.children if getattr(child, "name", None) is not None]
            if not child_tags:
                continue

            only_nested_p = True
            for child in p_tag.children:
                name = getattr(child, "name", None)
                if name is None:
                    if str(child).strip():
                        only_nested_p = False
                        break
                    continue
                if name != "p":
                    only_nested_p = False
                    break

            if only_nested_p:
                p_tag.unwrap()
                changed = True
                break

    return str(soup)

def format_html_fragment_with_prettier(fragment, prettier_binary, prettier_config, base_indent=""):
    """Format one HTML fragment with Prettier via stdin/stdout."""
    had_trailing_newline = fragment.endswith("\n")
    fragment = repair_nested_paragraph_wrappers(fragment)
    result = subprocess.run(
        [
            prettier_binary,
            "--parser",
            "html",
            "--print-width",
            str(prettier_config.get("print_width", 800)),
            "--tab-width",
            str(prettier_config.get("tab_width", 4)),
            "--html-whitespace-sensitivity",
            prettier_config.get("html_whitespace_sensitivity", "css"),
            "--prose-wrap",
            prettier_config.get("prose_wrap", "preserve"),
            "--embedded-language-formatting",
            prettier_config.get("embedded_language_formatting", "auto"),
            "--stdin-filepath",
            "/tmp/cleanmd-html-fragment.html",
        ],
        input=fragment,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stdout or result.stderr or "Prettier failed")

    formatted = result.stdout.rstrip("\n")
    formatted = apply_base_indentation(formatted, base_indent)
    if had_trailing_newline:
        formatted += "\n"
    return formatted

def format_html_blocks_in_text(string, prettier_binary, config, formatter=None):
    """Format configured top-level HTML blocks within one text slice."""
    tag_names = tuple(config.get("html_block_tags", DEFAULT_CLEANMD_CONFIG["html_block_tags"]))
    blocks = find_top_level_html_blocks(string, tag_names)

    replacements = []
    failures = []
    counts = {tag_name: 0 for tag_name in tag_names}
    if formatter is None:
        def formatter(fragment, base_indent):
            return format_html_fragment_with_prettier(
                fragment,
                prettier_binary,
                config.get("html_prettier", DEFAULT_CLEANMD_CONFIG["html_prettier"]),
                base_indent=base_indent,
            )

    for block in blocks:
        start = block["start"]
        end = block["end"]
        fragment = string[start:end]
        line_start = string.rfind("\n", 0, start) + 1
        indent_match = re.match(r'[ \t]*', string[line_start:start])
        base_indent = indent_match.group(0) if indent_match else ""

        try:
            formatted = formatter(fragment, base_indent)
            replacements.append((start, end, formatted))
            counts[block["tag"]] = counts.get(block["tag"], 0) + 1
        except Exception as exc:
            failures.append((start, block["tag"], str(exc)))

    for start, end, formatted in reversed(replacements):
        string = string[:start] + formatted + string[end:]

    return {
        "text": string,
        "blocks": blocks,
        "counts": counts,
        "failures": failures,
    }

def is_blockish_line(stripped):
    """Return True for lines that should not be treated as plain paragraph text."""
    if not stripped:
        return True

    block_patterns = [
        r'^([-*+]|\d+\.)\s+',
        r'^#{1,6}\s+',
        r'^>',
        r'^```',
        r'^~~~',
        r'^\|',
        r'^<',
    ]
    return any(re.match(pattern, stripped) for pattern in block_patterns)

def looks_like_complete_paragraph_line(stripped):
    """Heuristic for paragraph lines pasted from Word that should become separate paragraphs."""
    if is_blockish_line(stripped):
        return False

    words = re.findall(r'\b\w+\b', stripped)
    if len(words) < 5:
        return False

    return bool(re.search(r'[.!?]["\')\]]*$', stripped))

def promote_word_paragraph_breaks(string):
    """
    Promote likely Word single line breaks into paragraph breaks.

    This is intentionally conservative: it only inserts a blank line when two
    consecutive non-blank lines both look like complete prose paragraphs.
    """
    lines = string.splitlines()
    if len(lines) < 2:
        return string, 0

    newlines = []
    inserted = 0
    for index, line in enumerate(lines):
        newlines.append(line)

        if index == len(lines) - 1:
            continue

        current = line.strip()
        nxt = lines[index + 1].strip()

        if not current or not nxt:
            continue

        if looks_like_complete_paragraph_line(current) and looks_like_complete_paragraph_line(nxt):
            newlines.append('')
            inserted += 1

    return '\n'.join(newlines), inserted

def clean_md_result(string, config=None):
    """Apply the canonical markdown cleanup rules and return text plus summary stats."""
    if config is None:
        config = get_cleanmd_config()
    stats = {
        "regex_replacements": 0,
        "html_img_tags_normalized": 0,
        "html_external_links_hardened": 0,
        "word_paragraph_breaks_promoted": 0,
        "list_blank_lines_inserted": 0,
    }

    substitutions = [
        ('^( *)[-\\+·•ð§] +', '\\1- '),       # Replace decorative bullets with -
        ('^\\\\(\\d+\\.) +', '\\1 '),          # Replace escaped \1. etc with 1.
        ('^(?!\\s*---\\s*$)\\s*[#*_]{2,}\\s*$\n?', ''),              # Remove junk marker lines but preserve ---
        (' ', ' '),                      # Remove empty headings
        (r'(?<=\S) {2,}(?=\S)', ' '),                      # Collapse repeated internal spaces
        ('((?:#+|\\*|-|\\+|\\d+\\.)) {2,}', '\\1 '),      # Blank spaces before headings, bullets, numbers
        ('^( *)\\* +', '\\1- '),       # Canonicalize * bullets to -
        ('^( *)\\+ +', '\\1- '),       # Canonicalize + bullets to -
        ('<li><p>(.*?)</p></li>', '<li>\\1</li>'), # remove li>p
        ('(#+) +\\*\\*(.*?)\\*\\*', '\\1 \\2'),         # Un-bold headings
        ('> +([\\.,])', '>\\1'),               # Remove space between end tag and , or .
        ('\\[\\[\\d+\\?\\]\\]\\(#_ftn\\d+\\)', ''),   # Remove footnotes
        ('\\?*time\\d{8,}', '')               # Remove Moodle timestamps from image src
        # ('^\d+\W+(.*?)\W+\n', '## \\1')     # Make numbered lines into headings
    ]

    for old, new in substitutions:
        stats["regex_replacements"] += len(re.findall(old, string, flags=re.MULTILINE))
        string = re.sub(old, new, string, flags=re.MULTILINE)

    if config.get("normalize_html_fragments", True):
        string, html_stats = normalize_html_fragments(string, config=config)
        stats["html_img_tags_normalized"] = html_stats["img_tags_normalized"]
        stats["html_external_links_hardened"] = html_stats["external_links_hardened"]
    if config.get("promote_word_paragraph_breaks", True):
        string, promoted = promote_word_paragraph_breaks(string)
        stats["word_paragraph_breaks_promoted"] = promoted

    lines = string.splitlines()
    newlines = []
    inside_list = False
    blank_line = False
    for line in lines:
        # Check if the line starts with a list item marker (e.g., '-', '*', '+', or numbered list)
        stripped = line.strip()
        if re.match(r'^([-*+]|\d+\.)\s+', stripped):
            # Add a blank line in before first line item
            if not inside_list:
                newlines.append('')
                stats["list_blank_lines_inserted"] += 1
            newlines.append(line)
            inside_list = True
            blank_line = False
        # If the line is not a list item, assume we are out of a list
        elif stripped == '':
            blank_line = True
        else:
            # Add a blank line back in if the current line is not a list item
            # and the previous line was blank
            if blank_line or inside_list:
                newlines.append('')
                stats["list_blank_lines_inserted"] += 1
            newlines.append(line)
            inside_list = False
            blank_line = False
    return {
        "text": '\n'.join(newlines),
        "stats": stats,
    }

def clean_md_text(string, config=None):
    """Apply the canonical markdown cleanup rules to a string."""
    return clean_md_result(string, config=config)["text"]

def format_cleanmd_summary(stats):
    return (
        "CleanMD: {regex} replacements; {imgs} img tag(s); {links} external link(s); "
        "{paras} paragraph break(s); {lists} list spacer(s)"
    ).format(
        regex=stats["regex_replacements"],
        imgs=stats["html_img_tags_normalized"],
        links=stats["html_external_links_hardened"],
        paras=stats["word_paragraph_breaks_promoted"],
        lists=stats["list_blank_lines_inserted"],
    )

# Perform all text substitutions and string manipulations
def replacestrings(self, edit, config_overrides=None):
    # select all
    self.view.run_command("select_all")
    # convert to string
    sel = self.view.sel()
    string = self.view.substr(sel[0])
    config = build_cleanmd_config(overrides=config_overrides)
    result = clean_md_result(string, config=config)
    string = result["text"]

    # # Add Bootstrap support
    # bootstrap = '<link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css" integrity="sha384-Vkoo8x4CGsO3+Hhxv8T/Q5PaXtkKtu6ug5TOeNV6gBiFeWPGFN9MuhOf23Q9Ifjh" crossorigin="anonymous">\n<script src="https://code.jquery.com/jquery-3.4.1.slim.min.js" integrity="sha384-J6qa4849blE2+poT4WnyKhv5vZF5SrPo0iEjwBvKU7imGFAV0wwj1yYfoRSJoZ+n" crossorigin="anonymous"></script>\n<script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.0/dist/umd/popper.min.js" integrity="sha384-Q6E9RHvbIyZFJoft+2mJbHaEWldlvI9IOYy5n3zV9zzTtmI3UksdQRVvoxMfooAo" crossorigin="anonymous"></script>\n<script src="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/js/bootstrap.min.js" integrity="sha384-wfSDF2E50Y2D1uUdj0O3uMBJnjuUD4Ih7YwaYd1iqfktj0Uod8GCExl3Og8ifwB6" crossorigin="anonymous"></script>\n<link href="https://netdna.bootstrapcdn.com/font-awesome/4.7.0/css/font-awesome.min.css" rel="stylesheet">\n<style> h1, h2 {clear: both; color: maroon; } body {counter-reset: h1; } h1 {counter-reset: h2; counter-increment: h1; border-top: 10px double maroon; padding-top: 1em; margin-top: 3em !important} h1::before {content: counter(h1) ". "; color: black; font-weight: normal; font-size: 0.5em; vertical-align: middle; } h2 {counter-increment: h2; border-top: 2px dotted maroon; padding-top: 1em} h2::before {content: counter(h1) "." counter(h2) " "; color: black; font-weight: normal; font-size: 0.5em; vertical-align: middle; } h2[data-question]::before {content: attr(data-question) ": "; } h2[data-type]::after {content: " [" attr(data-type) "]"; font-size: 0.5em; font-weight: normal; color: black; vertical-align: middle; }</style>\n\n'

    # # Only add Bootstrap if it has not already been called
    # if "bootstrapcdn" not in string:
    #     string = bootstrap + string

    # Output to view
    self.view.replace(edit, sel[0], string)
    summary = format_cleanmd_summary(result["stats"])
    print(summary)
    self.view.set_status("CleanMD summary", summary)
    sublime.set_timeout(lambda: self.view.erase_status("CleanMD summary"), 8000)

    # Launch in browser
    if self.view.window() is not None:
        if config.get("run_formatter_after_clean", True):
            try:
                self.view.run_command("run_format", {"uid": "prettier", "type": "beautifier"})
            except Exception:
                pass
        if config.get("open_preview_after_clean", True):
            try:
                self.view.run_command("omni_markup_preview")
            except Exception:
                pass

class CleanMdRunTestsCommand(sublime_plugin.WindowCommand):

    def run(self):
        test_cases = [
            {
                "name": "Canonical bullets and preserved indentation",
                "input": "+ top level plus\n  * nested star\n    • nested decorative bullet",
                "expected": "\n- top level plus\n  - nested star\n    - nested decorative bullet"
            },
            {
                "name": "Ordered list spacing and paragraph separation",
                "input": "Steps\n1. one\n2. two",
                "expected": "Steps\n\n1. one\n2. two"
            },
            {
                "name": "Collapse repeated blank lines between paragraphs",
                "input": "First paragraph\n\n\n\nSecond paragraph",
                "expected": "First paragraph\n\nSecond paragraph"
            },
            {
                "name": "Collapse blank lines before a list",
                "input": "Intro\n\n\n\n- one\n- two",
                "expected": "Intro\n\n- one\n- two"
            },
            {
                "name": "Remove blank lines inside a list block",
                "input": "- one\n\n- two",
                "expected": "\n- one\n- two"
            },
            {
                "name": "Preserve horizontal rule",
                "input": "Before\n\n---\n\nAfter",
                "expected": "Before\n\n---\n\nAfter"
            },
            {
                "name": "Remove junk marker-only lines",
                "input": "Before\n***\n###\n__\nAfter",
                "expected": "Before\nAfter"
            },
            {
                "name": "Unbold headings without losing heading level",
                "input": "# **Heading One**\n## **Heading Two**",
                "expected": "# Heading One\n## Heading Two"
            },
            {
                "name": "Normalize marker spacing",
                "input": "#  Heading\n-   Bullet\n12.   Numbered item",
                "expected": "# Heading\n\n- Bullet\n12. Numbered item"
            },
            {
                "name": "Do not treat numbered prose as a list item",
                "input": "2024 was a big year\nNext line",
                "expected": "2024 was a big year\nNext line"
            },
            {
                "name": "Remove non-breaking spaces and repeated internal spaces",
                "input": "This has  too   many spaces",
                "expected": "This has too many spaces"
            },
            {
                "name": "Promote likely Word paragraph breaks",
                "input": "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.\nUt enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.\nExcepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.",
                "expected": "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.\n\nUt enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.\n\nExcepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
            },
            {
                "name": "Do not promote paragraph breaks before lists",
                "input": "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.\n- One\n- Two",
                "expected": "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.\n\n- One\n- Two"
            },
            {
                "name": "Insert blank line before paragraph after list",
                "input": "Leading para\n- one\n- two\n- three\nTrailing para",
                "expected": "Leading para\n\n- one\n- two\n- three\n\nTrailing para"
            },
            {
                "name": "Simplify li paragraph wrappers",
                "input": "<ul>\n<li><p>One</p></li>\n<li><p>Two</p></li>\n</ul>",
                "expected": "<ul>\n<li>One</li>\n<li>Two</li>\n</ul>"
            },
            {
                "name": "Remove only width from image styles",
                "input": '<p><img src="image.png" style="width: 300px; border: 1px solid red; float: right"></p>',
                "expected": '<p><img src="image.png" style="border: 1px solid red; float: right"/></p>'
            },
            {
                "name": "Add target and rel to external HTML links only",
                "input": '<p><a href="https://example.com">External</a> and <a href="/internal">Internal</a></p>',
                "expected": '<p><a href="https://example.com" rel="noopener noreferrer" target="_blank">External</a> and <a href="/internal">Internal</a></p>'
            },
            {
                "name": "Remove footnote artifacts and Moodle timestamps",
                "input": 'Footnote here[[3?]](#_ftn3)\n![img](example.png?time1712345678)',
                "expected": 'Footnote here\n![img](example.png)'
            },
            {
                "name": "Remove trailing blank lines at end of file",
                "input": "Last paragraph\n\n\n",
                "expected": "Last paragraph"
            },
            {
                "name": "Disable Word paragraph promotion via config",
                "input": "Sentence one.\nSentence two.",
                "expected": "Sentence one.\nSentence two.",
                "config": {"promote_word_paragraph_breaks": False}
            },
            {
                "name": "Disable HTML fragment normalization via config",
                "input": '<p><a href="https://example.com">External</a> <img src="image.png" style="width: 300px; border: 1px solid red"></p>',
                "expected": '<p><a href="https://example.com">External</a> <img src="image.png" style="width: 300px; border: 1px solid red"></p>',
                "config": {"normalize_html_fragments": False}
            }
        ]

        html_block_test = {
            "name": "Selection-slice HTML formatting leaves surrounding Markdown untouched",
            "input": "## Heading\n<figure>\n<div>Text</div>\n</figure>\n\nTrailing paragraph",
            "expected": "## Heading\nFORMATTED_BLOCK\n\nTrailing paragraph",
            "counts": {"figure": 1, "div": 0},
        }

        results = []
        passed = 0

        for case in test_cases:
            config = build_cleanmd_config(overrides=case.get("config", {}))
            actual = clean_md_text(case["input"], config=config)
            ok = actual == case["expected"]
            if ok:
                passed += 1
                results.append("PASS: {}".format(case["name"]))
            else:
                results.append("FAIL: {}".format(case["name"]))
                results.append("INPUT:")
                results.append(case["input"])
                results.append("EXPECTED:")
                results.append(case["expected"])
                results.append("ACTUAL:")
                results.append(actual)
                results.append("")

        html_result = format_html_blocks_in_text(
            html_block_test["input"],
            prettier_binary="",
            config=get_cleanmd_config(),
            formatter=lambda fragment, base_indent: "FORMATTED_BLOCK\n",
        )
        html_ok = (
            html_result["text"] == html_block_test["expected"]
            and html_result["counts"].get("figure", 0) == html_block_test["counts"]["figure"]
            and html_result["counts"].get("div", 0) == html_block_test["counts"]["div"]
            and not html_result["failures"]
        )
        if html_ok:
            passed += 1
            results.append("PASS: {}".format(html_block_test["name"]))
        else:
            results.append("FAIL: {}".format(html_block_test["name"]))
            results.append("INPUT:")
            results.append(html_block_test["input"])
            results.append("EXPECTED:")
            results.append(html_block_test["expected"])
            results.append("ACTUAL:")
            results.append(html_result["text"])
            results.append("COUNTS:")
            results.append(str(html_result["counts"]))
            results.append("")

        report = "CleanMD tests: {}/{} passed\n\n{}".format(
            passed,
            len(test_cases) + 1,
            "\n".join(results)
        )

        view = self.window.new_file()
        view.set_name("CleanMD Test Results")
        view.set_scratch(True)
        view.assign_syntax("Packages/Text/Plain text.tmLanguage")
        view.run_command("append", {"characters": report})

class CleanMdPrettierdSmokeTestCommand(sublime_plugin.WindowCommand):

    def run(self):
        prettierd = shutil.which("prettierd") or "/opt/homebrew/bin/prettierd"
        prettier = shutil.which("prettier") or "/opt/homebrew/bin/prettier"
        sample = (
            '<figure><img src="x"><figcaption><small>'
            '<a href="https://example.com">Link</a>'
            '</small></figcaption></figure>'
        )

        report_lines = [
            "CleanMD prettierd smoke test",
            "",
            "Prettierd binary: {}".format(prettierd),
            "Prettier binary: {}".format(prettier),
            "",
            "Input:",
            sample,
            "",
        ]

        if not os.path.exists(prettierd):
            report_lines.extend([
                "Result: prettierd binary not found",
                "",
                "Expected location was not available. If prettierd is installed,",
                "check whether Sublime can see it in PATH.",
            ])
        else:
            command_variants = [
                {
                    "label": "Prettierd variant 1: invoke <path>",
                    "args": [prettierd, "invoke", "/tmp/cleanmd-prettierd-smoke.html"],
                },
                {
                    "label": "Prettierd variant 2: invoke -- /tmp/cleanmd-prettierd-smoke.html",
                    "args": [prettierd, "invoke", "--", "/tmp/cleanmd-prettierd-smoke.html"],
                },
                {
                    "label": "Prettierd variant 3: invoke /tmp",
                    "args": [prettierd, "invoke", "/tmp"],
                },
            ]

            for variant in command_variants:
                report_lines.extend([
                    variant["label"],
                    "Command: {}".format(" ".join(variant["args"])),
                    "",
                ])

                try:
                    result = subprocess.run(
                        variant["args"],
                        input=sample,
                        text=True,
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
                    report_lines.extend([
                        "Exit code: {}".format(result.returncode),
                        "",
                        "STDOUT:",
                        result.stdout if result.stdout else "<empty>",
                        "",
                        "STDERR:",
                        result.stderr if result.stderr else "<empty>",
                        "",
                    ])
                except Exception as exc:
                    report_lines.extend([
                        "Result: invocation raised an exception",
                        repr(exc),
                        "",
                    ])

        report_lines.extend([
            "Prettier stdin/stdout test",
            "",
        ])

        if not os.path.exists(prettier):
            report_lines.extend([
                "Result: prettier binary not found",
                "",
            ])
        else:
            prettier_args = [
                prettier,
                "--parser",
                "html",
                "--stdin-filepath",
                "/tmp/cleanmd-prettier-smoke.html",
            ]
            report_lines.extend([
                "Command: {}".format(" ".join(prettier_args)),
                "",
            ])

            try:
                result = subprocess.run(
                    prettier_args,
                    input=sample,
                    text=True,
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
                report_lines.extend([
                    "Exit code: {}".format(result.returncode),
                    "",
                    "STDOUT:",
                    result.stdout if result.stdout else "<empty>",
                    "",
                    "STDERR:",
                    result.stderr if result.stderr else "<empty>",
                ])
            except Exception as exc:
                report_lines.extend([
                    "Result: invocation raised an exception",
                    repr(exc),
                ])

        self._show_report("\n".join(report_lines))

    def _show_report(self, report):
        view = self.window.new_file()
        view.set_name("CleanMD Prettierd Smoke Test")
        view.set_scratch(True)
        view.assign_syntax("Packages/Text/Plain text.tmLanguage")
        view.run_command("append", {"characters": report})

class CleanMdFormatHtmlBlocksCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        config = get_cleanmd_config()
        prettier = shutil.which("prettier") or "/opt/homebrew/bin/prettier"
        if not os.path.exists(prettier):
            sublime.message_dialog(
                "CleanMD could not find prettier.\n\nExpected: {}".format(prettier)
            )
            return

        non_empty_regions = [region for region in self.view.sel() if not region.empty()]
        failures = []
        counts = {"figure": 0, "div": 0}
        total_blocks = 0

        if non_empty_regions:
            scope_label = "selection(s)"
            for region in sorted(non_empty_regions, key=lambda r: r.begin(), reverse=True):
                original = self.view.substr(region)
                result = format_html_blocks_in_text(original, prettier, config)
                total_blocks += len(result["blocks"])
                for tag, count in result["counts"].items():
                    counts[tag] = counts.get(tag, 0) + count
                for start, tag, error in result["failures"]:
                    failures.append((region.begin() + start, tag, error))
                if original != result["text"]:
                    self.view.replace(edit, region, result["text"])
        else:
            scope_label = "file"
            full_region = sublime.Region(0, self.view.size())
            original = self.view.substr(full_region)
            result = format_html_blocks_in_text(original, prettier, config)
            total_blocks = len(result["blocks"])
            counts = result["counts"]
            failures = result["failures"]
            if original != result["text"]:
                self.view.replace(edit, full_region, result["text"])

        if total_blocks == 0:
            if non_empty_regions:
                sublime.status_message("CleanMD: no configured top-level HTML blocks found in selection(s)")
            else:
                sublime.status_message("CleanMD: no configured top-level HTML blocks found")
            return

        figures = counts.get("figure", 0)
        divs = counts.get("div", 0)
        if failures:
            message = "BirdyOz - Format HTML Blocks cleaned {} figure(s) and {} div(s) in {}; {} block(s) failed".format(
                figures, divs, scope_label, len(failures)
            )
        else:
            message = "BirdyOz - Format HTML Blocks cleaned {} figure(s) and {} div(s) in {}".format(
                figures, divs, scope_label
            )

        print(message)
        for start, tag, error in failures:
            print("CleanMD HTML format failed for {} at {}: {}".format(tag, start, error))
        sublime.status_message(message)
