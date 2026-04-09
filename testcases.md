<!--
This file contains representative input fixtures for GB-clean-MD.py.
Each test case includes:

- INPUT: sample source text
- EXPECTED: the cleaned output, recorded in HTML comments
-->

# Test Case 1: Canonical bullets and preserved indentation

INPUT:

```md
- top level plus
    - nested star
        - nested decorative bullet
```

<!--
EXPECTED:

- top level plus
  - nested star
    - nested decorative bullet
-->

# Test Case 2: Ordered list spacing and paragraph separation

INPUT:

```md
Steps

1. one
2. two
```

<!--
EXPECTED:
Steps

1. one
2. two
-->

# Test Case 3: Collapse repeated blank lines between paragraphs

INPUT:

```md
First paragraph

Second paragraph
```

<!--
EXPECTED:
First paragraph

Second paragraph
-->

# Test Case 4: Collapse blank lines before a list

INPUT:

```md
Intro

- one
- two
```

<!--
EXPECTED:
Intro

- one
- two
-->

# Test Case 5: Remove blank lines inside a list block

INPUT:

```md
- one
- two
```

<!--
EXPECTED:

- one
- two
-->

# Test Case 6: Preserve horizontal rule ---

INPUT:

```md
Before

---

After
```

<!--
EXPECTED:
Before

---

After
-->

# Test Case 7: Remove junk marker-only lines

INPUT:

```md
Before
After
```

<!--
EXPECTED:
Before
After
-->

# Test Case 8: Unbold headings without losing heading level

INPUT:

```md
# Heading One

## Heading Two
```

<!--
EXPECTED:
# Heading One
## Heading Two
-->

# Test Case 9: Normalize marker spacing

INPUT:

```md
# Heading

- Bullet

12. Numbered item
```

<!--
EXPECTED:
# Heading

- Bullet
12. Numbered item
-->

# Test Case 10: Do not treat numbered prose as a list item

INPUT:

```md
2024 was a big year
Next line
```

<!--
EXPECTED:
2024 was a big year
Next line
-->

# Test Case 11: Remove non-breaking spaces and repeated internal spaces

INPUT:

```md
This has too many spaces
```

<!--
EXPECTED:
This has too many spaces
-->

# Test Case 12: Simplify li paragraph wrappers

INPUT:

```html
<ul>
    <li>One</li>
    <li>Two</li>
</ul>
```

<!--
EXPECTED:
<ul>
<li>One</li>
<li>Two</li>
</ul>
-->

# Test Case 13: Remove only width from image styles

INPUT:

```html
<p><img src="image.png" style="border: 1px solid red; float: right" /></p>
```

<!--
EXPECTED:
<p><img src="image.png" style="border: 1px solid red; float: right"/></p>
-->

# Test Case 14: Add target and rel to external HTML links only

INPUT:

```html
<p><a href="https://example.com" rel="noopener noreferrer" target="_blank">External</a> and <a href="/internal">Internal</a></p>
```

<!--
EXPECTED:
<p><a href="https://example.com" rel="noopener noreferrer" target="_blank">External</a> and <a href="/internal">Internal</a></p>
-->

# Test Case 15: Remove footnote artifacts and Moodle timestamps

INPUT:

```md
Footnote here
![img](example.png)
```

<!--
EXPECTED:
Footnote here
![img](example.png)
-->

# Test Case 16: Remove trailing blank lines at end of file

INPUT:

```md
Last paragraph
```

<!--
EXPECTED:
Last paragraph
-->
