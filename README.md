# CleanMD for Sublime Text

`CleanMD` is a Sublime Text command for tidying messy Markdown, especially Markdown produced from Word or other document-conversion workflows.

The package now has a narrow focus:

- clean Markdown and mixed Markdown/HTML
- normalise list markers and spacing
- remove common conversion artefacts
- keep raw HTML links and images tidy
- optionally format top-level HTML blocks in mixed Markdown files

HTML-to-Markdown conversion is no longer handled here. That responsibility now lives in the `MD-to-HTML` package via `StripMarkupCommand`.

## What CleanMD does

When run on a Markdown document, `CleanMD` applies a string-to-string cleanup pass that:

- standardises unordered list markers to `-`
- preserves leading indentation for nested list items
- normalises spacing after headings, bullets, and numbered list markers
- removes junk marker-only lines while preserving `---` horizontal rules
- removes repeated internal spaces and non-breaking spaces
- un-bolds headings such as `# **Heading**` to `# Heading`
- collapses repeated blank lines
- ensures a blank line before list blocks
- removes blank lines between consecutive list items
- removes Word-style footnote artefacts
- removes Moodle-style `?time...` cache-busting suffixes from image URLs
- simplifies `<li><p>...</p></li>` to `<li>...</li>`
- removes only `width:` from inline image styles
- adds `target="_blank"` and `rel="noopener noreferrer"` to external raw HTML links

## HTML Block Formatting

`CleanMD` also provides a separate command for formatting top-level HTML fragments in mixed Markdown files.

`BirdyOz - Format HTML Blocks`:

- targets top-level `figure` and `div` blocks only
- leaves surrounding Markdown untouched
- formats each block independently with `prettier`
- uses a wide print width and 4-space indentation to match the existing Sublime formatting style
- applies a narrow repair for invalid nested paragraph wrappers such as `<p><p>...</p></p>` before formatting

This command is intended for occasional structural cleanup of large mixed Markdown files rather than frequent everyday formatting.

## DOCX workflow

If the current file is a `.docx`, the command uses `pandoc` to convert it to GitHub-flavoured Markdown, extracts media into an `assets` directory, opens the generated `.md`, and then you can run the normal cleanup flow on that Markdown file.

## Commands

This package currently provides:

- `clean_md`
- `clean_md_run_tests`
- `clean_md_format_html_blocks`
- `clean_md_prettierd_smoke_test`

Command palette caption:

- `BirdyOz - Clean MarkDown`
- `BirdyOz - Format HTML Blocks`
- `BirdyOz - Run CleanMD Tests`
- `BirdyOz - Prettierd Smoke Test`

## Tests

`CleanMD` includes a small built-in regression suite that runs inside Sublime Text's Python runtime.

Run it from the console with:

```python
window.run_command("clean_md_run_tests")
```

It opens a scratch buffer named `CleanMD Test Results` with pass/fail output.

## Dependencies

Optional integrations used by the cleanup command:

- `pandoc` for `.docx` to Markdown conversion
- a `run_format` command such as Prettier, if installed
- `prettier` on the command line for `BirdyOz - Format HTML Blocks`
- `OmniMarkupPreviewer`, if installed

The cleaner still works if the formatter or preview command is unavailable.

## Keyboard Shortcut

Default macOS shortcut:

- <kbd>CMD</kbd> + <kbd>Control</kbd> + <kbd>\\</kbd>
