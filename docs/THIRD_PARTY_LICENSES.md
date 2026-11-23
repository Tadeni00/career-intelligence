# Third-party licensing and distribution notes

Career Intelligence's **original project code** is published under the [MIT License](../LICENSE). This does not relicense dependencies or any third-party content. License terms of downloaded packages, data, job listings, user-provided CVs and generated documents remain their respective owners' terms.

## Important reciprocal-licensing dependency

- **PyMuPDF / MuPDF**, declared as `pymupdf>=1.24` in `pyproject.toml`, is available under **GNU AGPLv3 or a separate commercial license**. Source: https://pymupdf.io/licensing . The MIT license of this repository does **not** override PyMuPDF's requirements. Users distributing or deploying the integrated application must independently confirm AGPL obligations, compatibility and any notice/source requirements; get appropriate licensing advice where necessary. Do not claim the whole Docker image is MIT-only. The code here was not relicensed as AGPL and this document does not determine whether the particular integration creates a combined work.
- The React interface uses Mantine and Tabler Icons packages distributed under MIT terms (see https://mantine.dev/getting-started/ and https://github.com/tabler/tabler-icons). Retain applicable third-party notices and check all transitive dependencies in installed distributions.

## Other release obligations

- Review package metadata and bundled licenses from `npm ci` and the pinned Python environment before distributing images or compiled installers. This is a targeted dependency review, not a complete software composition analysis.
- Do not redistribute copied job advertisements, employer logos, uploaded candidate CVs, or provider datasets without checking separate permission/terms.
- The public Git history previously contained five candidate CV/profile exports. They were removed from the current tree only; **history and external clones/caches may continue to contain them**. See [SEC-003](https://github.com/Tadeni00/career-intelligence/issues/3). No history rewrite has been authorized.

Individual local users can install dependencies under their actual licenses. Do not publish the unauthenticated API publicly.
