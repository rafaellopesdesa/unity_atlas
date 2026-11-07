# ATLAS Analysis on Unity

A growing guide to using UMass Unity as an analysis facility for ATLAS.

The first chapter, **Setting up the environment**, covers Slurm CPU/GPU allocations, CVMFS, an EL9 container through ATLASLocalRootBase and Apptainer, software selection, optional Bash shortcuts, and troubleshooting.

## Publish with GitHub Pages

In **Settings → Pages**, select **Deploy from a branch**, **main**, and **/ (root)**. Save. The expected project URL is <https://rafaellopesdesa.github.io/unity_atlas/> after Pages is enabled and its deployment finishes.

The rendered HTML, CSS, JavaScript, and `.nojekyll` are committed. No Jekyll theme, package installation, or custom build workflow is needed to serve this version. Pages activation is left to the repository owner.

## Edit and extend

1. Edit the Markdown sources in `docs/`.
2. For a new chapter, add its metadata to `docs/pages.json` in navigation order.
3. With Python 3 and [Pandoc](https://pandoc.org/installing.html) installed, run `python3 tools/build_site.py` from any directory. Initial build: Pandoc 3.1.3.
4. Run `python3 tools/check_site.py`, `node --check assets/site.js`, and `bash -n examples/atlas-bashrc.sh`.
5. Commit the sources **and** regenerated HTML/search index together.

Serve the repository root locally with `python3 -m http.server 8000`, then open <http://localhost:8000/>. The site also uses relative asset links so it works under the GitHub project subpath. `tools/template.html` and `assets/style.css` define the shared layout. All content and navigation remain readable without JavaScript; search, copy buttons, and the mobile menu are progressive enhancements.

## Validation status

Documentation reviewed on 7 November 2026 against Unity, ATLAS, US ATLAS AF, and Apptainer references. Rafael confirmed on Unity that **`/work` is visible inside the container without `-m /work`**; the standard commands therefore omit that option. **Full end-to-end validation is still pending**, including software setup and GPU passthrough. No particular AnalysisBase/Athena release or group storage path is assumed.

The canonical ATLAS documentation returned HTTP 403 from the research environment. The equivalent prerequisites page in its CERN-hosted documentation mirror was readable and was used to cross-check the EL9 setup sequence: <https://shahzad.web.cern.ch/shahzad/atlas-software-docs/athena/developers/tutorial/prerequisites/>. Reader-facing links point to the canonical documentation.

To record a Unity smoke test, include the date, compute-node hostname and architecture, Apptainer version and runtime selected by ALRB, resolved container image, `/etc/os-release` inside the container, storage visibility, exact ATLAS release/platform, and ROOT/PyROOT checks. For a GPU allocation, also verify passthrough and the Slurm-assigned device selection with the intended CUDA framework.

## Primary references

- <https://atlas-software.docs.cern.ch/>
- <https://docs.unity.rc.umass.edu/documentation/>
- <https://usatlas.github.io/af-docs/containers/apptainer/usage/>
- <https://apptainer.org/docs/user/latest/gpu.html>
