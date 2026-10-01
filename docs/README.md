# WashO: Project Documentation

| File | What it is |
|---|---|
| [01_synopsis.md](01_synopsis.md) | Synopsis (about 4 pages): title, abstract, problem, objectives, scope, existing vs proposed system, modules, requirements, Gantt chart |
| [02_project_report.md](02_project_report.md) | Full report: Introduction, Existing System Study, Requirement Analysis, Feasibility, System Design, Implementation, Testing, Limitations, Future Enhancements, Conclusion, References |
| [03_diagrams.md](03_diagrams.md) | E-R diagram, DFD Level 0/1/2, Use Case, Class, Sequence (booking, tagging, delivery), Activity, State, Deployment |
| [04_data_dictionary.md](04_data_dictionary.md) | Every table: field, type, constraint, description (generated from the code) |
| [05_test_cases.md](05_test_cases.md) | Test case table: ID, description, input, expected, actual, status |
| [06_screenshots.md](06_screenshots.md) | List of 35 screenshots to capture, with logins and captions |
| [07_viva_prep.md](07_viva_prep.md) | 40 likely viva questions with short answers |
| [diagrams/](diagrams/) | Every diagram as a PNG, ready to insert into Word |

## Making the Word / PDF report
1. Open each `.md` file in VS Code and press **Ctrl + Shift + V** to preview it, or view it on GitHub.
2. Copy the text into the college's Word template (certificate, declaration and acknowledgement come first).
3. Insert the PNG files from `diagrams/` where each diagram belongs.
4. Insert your screenshots (see `06_screenshots.md`) in the Implementation / Testing chapters.
5. Fill in your name, roll number, guide and college on the title page and in the synopsis table.

## Keeping the docs up to date
- Data dictionary: `venv\Scripts\python scripts\gen_data_dictionary.py`
- Diagram PNGs: edit the Mermaid code in `03_diagrams.md`, then export again at <https://mermaid.live>
