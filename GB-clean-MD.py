import sublime, sublime_plugin, re, os
from bs4 import BeautifulSoup


class CleanMd(sublime_plugin.TextCommand):

    def run(self, edit):

        file_name = self.view.file_name() or ""

        if ".docx" in file_name:
            dir_name = os.path.dirname(file_name)
            assets_dir = dir_name.replace(" ","\\ ") + "/assets"
            file_name = file_name.replace(" ","\\ ")
            md_name = file_name.replace(".docx", ".md")
            pandoc = "pandoc -f docx -t gfm " + file_name + " -o " + md_name + " --extract-media=" + assets_dir + " --wrap=none --columns=8000 --tab-stop=4"
            os.system(pandoc)
            newView = self.view.window().open_file(md_name.replace("\\ "," "))

        else:
            replacestrings(self, edit)

def normalize_html_fragments(string):
    """Safely normalize a few HTML attributes inside mixed HTML/Markdown."""
    if "<" not in string or ">" not in string:
        return string

    soup = BeautifulSoup(string, "html.parser")

    for img in soup.find_all("img"):
        style = img.get("style")
        if not style:
            continue

        rules = []
        for rule in style.split(";"):
            rule = rule.strip()
            if not rule:
                continue
            if rule.lower().startswith("width:"):
                continue
            rules.append(rule)

        if rules:
            img["style"] = "; ".join(rules)
        else:
            del img["style"]

    for a in soup.find_all("a"):
        href = a.get("href", "")
        if a.has_attr("target"):
            del a["target"]
        if a.has_attr("rel"):
            del a["rel"]
        if re.match(r"^https?://", href, flags=re.IGNORECASE):
            a["target"] = "_blank"
            a["rel"] = ["noopener", "noreferrer"]

    return str(soup)

def clean_md_text(string):
    """Apply the canonical markdown cleanup rules to a string."""
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
        string = re.sub(old, new, string, flags=re.MULTILINE)

    string = normalize_html_fragments(string)

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
            newlines.append(line)
            inside_list = True
            blank_line = False
        # If the line is not a list item, assume we are out of a list
        elif stripped == '':
            blank_line = True
        else:
            # Add a blank line back in if the current line is not a list item
            # and the previous line was blank
            if blank_line:
                newlines.append('')
            newlines.append(line)
            inside_list = False
            blank_line = False
    return '\n'.join(newlines)

# Perform all text substitutions and string manipulations
def replacestrings(self, edit):
    # select all
    self.view.run_command("select_all")
    # convert to string
    sel = self.view.sel()
    string = self.view.substr(sel[0])
    string = clean_md_text(string)

    # # Add Bootstrap support
    # bootstrap = '<link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css" integrity="sha384-Vkoo8x4CGsO3+Hhxv8T/Q5PaXtkKtu6ug5TOeNV6gBiFeWPGFN9MuhOf23Q9Ifjh" crossorigin="anonymous">\n<script src="https://code.jquery.com/jquery-3.4.1.slim.min.js" integrity="sha384-J6qa4849blE2+poT4WnyKhv5vZF5SrPo0iEjwBvKU7imGFAV0wwj1yYfoRSJoZ+n" crossorigin="anonymous"></script>\n<script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.0/dist/umd/popper.min.js" integrity="sha384-Q6E9RHvbIyZFJoft+2mJbHaEWldlvI9IOYy5n3zV9zzTtmI3UksdQRVvoxMfooAo" crossorigin="anonymous"></script>\n<script src="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/js/bootstrap.min.js" integrity="sha384-wfSDF2E50Y2D1uUdj0O3uMBJnjuUD4Ih7YwaYd1iqfktj0Uod8GCExl3Og8ifwB6" crossorigin="anonymous"></script>\n<link href="https://netdna.bootstrapcdn.com/font-awesome/4.7.0/css/font-awesome.min.css" rel="stylesheet">\n<style> h1, h2 {clear: both; color: maroon; } body {counter-reset: h1; } h1 {counter-reset: h2; counter-increment: h1; border-top: 10px double maroon; padding-top: 1em; margin-top: 3em !important} h1::before {content: counter(h1) ". "; color: black; font-weight: normal; font-size: 0.5em; vertical-align: middle; } h2 {counter-increment: h2; border-top: 2px dotted maroon; padding-top: 1em} h2::before {content: counter(h1) "." counter(h2) " "; color: black; font-weight: normal; font-size: 0.5em; vertical-align: middle; } h2[data-question]::before {content: attr(data-question) ": "; } h2[data-type]::after {content: " [" attr(data-type) "]"; font-size: 0.5em; font-weight: normal; color: black; vertical-align: middle; }</style>\n\n'

    # # Only add Bootstrap if it has not already been called
    # if "bootstrapcdn" not in string:
    #     string = bootstrap + string

    # Output to view
    self.view.replace(edit, sel[0], string)

    # Launch in browser
    if self.view.window() is not None:
        try:
            self.view.run_command("run_format", {"uid": "prettier", "type": "beautifier"})
        except Exception:
            pass
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
            }
        ]

        results = []
        passed = 0

        for case in test_cases:
            actual = clean_md_text(case["input"])
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

        report = "CleanMD tests: {}/{} passed\n\n{}".format(
            passed,
            len(test_cases),
            "\n".join(results)
        )

        view = self.window.new_file()
        view.set_name("CleanMD Test Results")
        view.set_scratch(True)
        view.assign_syntax("Packages/Text/Plain text.tmLanguage")
        view.run_command("append", {"characters": report})
