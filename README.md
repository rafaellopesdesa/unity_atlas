# ATLAS Analysis on Unity

A growing guide to using UMass Unity as an analysis facility for ATLAS.

The first chapter, **Setting up the environment**, covers one-time creation of `/work/${USER_PI}/${USER}` and `/project/${USER_PI}/${USER}`, persistent `USER_PI` configuration, Slurm CPU/GPU allocations, CVMFS, an EL9 container through ATLASLocalRootBase and Apptainer, software selection, Bash shortcuts, and troubleshooting. Later chapters assume those directory settings and interactive shortcuts are configured.

The second chapter, **Submitting jobs with Slurm**, explains worker-side environment setup and provides a self-contained PyROOT smoke test. Downloadable scripts are in `examples/slurm/`; the rendered chapter is `submitting-jobs/index.html`.

The third chapter, **Using Pixi**, covers installation in the user area, persistent `PATH` configuration, personal tools with `pixi global`, and `pixi install` / `pixi run` for existing projects. It links to the Carpentries introduction for creating environments and adding packages. The rendered chapter is `using-pixi/index.html`.

The fourth chapter, **Using VS Code**, covers local SSH configuration, compute allocations, ordinary Remote SSH, a container RemoteCommand launcher, and Remote Tunnels started inside EL9. It includes Python Run/debug checks, notebook kernel selection, a remote Jupyter alternative, and session cleanup. Downloadable helpers and examples are in `examples/vscode/`; the rendered chapter is `using-vscode/index.html`.

The fifth chapter, **Using JupyterLab**, covers launching a notebook server from a Pixi project in a Slurm session, choosing Ubuntu or EL9, connecting a local browser through SSH, selecting and checking the kernel, and managing session lifetime. It reuses the environment and Pixi setup. The rendered chapter is `using-jupyterlab/index.html`.

The sixth chapter, **Codex Agents**, gives the full per-user workflow: start Codex inside EL9 with an ATLAS release, install isolated Rucio/AMI MCP clients, create a VOMS proxy, configure stdio servers, check authenticated access, and renew/resume sessions. It assumes Pixi is installed as described in the earlier chapter. Downloadable configuration, a Pixi manifest, an environment launcher, and project instructions are in `examples/codex/`; the rendered chapter is `codex-agents/index.html`.

## Publish with GitHub Pages

In **Settings → Pages**, select **Deploy from a branch**, **main**, and **/ (root)**. Save. The expected project URL is <https://rafaellopesdesa.github.io/unity_atlas/> after Pages is enabled and its deployment finishes.

The rendered HTML, CSS, JavaScript, and `.nojekyll` are committed. No Jekyll theme, package installation, or custom build workflow is needed to serve this version. Pages activation is left to the repository owner.

## Edit and extend

1. Edit the Markdown sources in `docs/`.
2. For a new chapter, add its metadata to `docs/pages.json` in navigation order.
3. With Python 3.11 or newer and [Pandoc](https://pandoc.org/installing.html) installed, run `python3 tools/build_site.py` from any directory. Initial build: Pandoc 3.1.3.
4. Run `python3 tools/check_site.py`, `node --check assets/site.js`, and `bash -n examples/atlas-bashrc.sh`.
5. If editing examples displayed in full, update their matching code blocks in `docs/` too. The site checker verifies that these displayed examples match the downloads, checks Bash syntax, JSON, and TOML, and parses the Python example.
6. Commit the sources **and** regenerated HTML/search index together.

Serve the repository root locally with `python3 -m http.server 8000`, then open <http://localhost:8000/>. The site also uses relative asset links so it works under the GitHub project subpath. `tools/template.html` and `assets/style.css` define the shared layout. All content and navigation remain readable without JavaScript; search, copy buttons, and the mobile menu are progressive enhancements.

## Validation status

Documentation reviewed on 7 November 2026 against Unity, ATLAS, US ATLAS AF, and Apptainer references. Rafael confirmed on Unity that **`/work` is visible inside the container without `-m /work`**; the standard commands therefore omit that option. **Rafael has now tested the interactive recipe successfully on Unity.** He also confirmed that `nvidia-smi` works inside EL9 when `--nv` is explicitly passed through `ALRB_CONT_CMDOPTS`. Both GPU recipes now use this form; `examples/atlas-bashrc.sh` supplies an optional `atlas_gpu` function for interactive use. The exact node, release, and GPU framework were not recorded. The new batch recipe has passed local syntax, link, and simulated execution checks, but still needs its first end-to-end Unity test. No particular AnalysisBase/Athena release or group storage path is assumed.

The canonical ATLAS documentation returned HTTP 403 from the research environment. The equivalent prerequisites page in its CERN-hosted documentation mirror was readable and was used to cross-check the EL9 setup sequence: <https://shahzad.web.cern.ch/shahzad/atlas-software-docs/athena/developers/tutorial/prerequisites/>. Reader-facing links point to the canonical documentation.

The VS Code chapter was reviewed on 8 November 2026 against Unity, ATLAS, Microsoft, DCCN, and Slurm sources. Local mocked launcher checks cover bootstrap input preservation, ATLAS alias setup, job validation, and failure propagation. Actual Unity Run/F5, notebook, reconnect, and GPU-framework tests remain pending. The SSH container method is a CPU-first prototype; the tunnel method starts directly in the existing configured allocation and is the preferred initial GPU test. No Unity support for outbound tunnels is assumed.

The Codex chapter was reviewed on 8 November 2026 against OpenAI, Pixi, and the Rucio/AMI MCP code and conda-forge recipes. It selects Rucio MCP 0.10.0, AMI MCP 0.3.1, and Python 3.11. Local launcher checks cover environment isolation, argument and stdio preservation, proxy/account preflight, and exit-status propagation. The dependency solve, Codex sign-in and sandbox inside Apptainer, and live authenticated Rucio/AMI calls remain to be tested on Unity. The chapter provides explicit ROOT, Rucio identity, and remote AMI checks for that first run.

The Pixi chapter was reviewed on 8 November 2026 against the official installation, global-tool, install/run, and lock-file documentation. Local checks cover Bash syntax and rendered links. Pixi installation and package execution on Unity remain to be tested.

The JupyterLab chapter was reviewed on 8 November 2026 against Unity, Pixi, Jupyter/IPython, OpenSSH, and Apptainer documentation. Local checks cover Bash/Python syntax, navigation, and internal links. Kernel registration, browser access through the tunnel, package imports, and reconnection still need an end-to-end Unity test.

To record a Unity smoke test, include the date, compute-node hostname and architecture, Apptainer version and runtime selected by ALRB, resolved container image, `/etc/os-release` inside the container, storage visibility, exact ATLAS release/platform, and ROOT/PyROOT checks. For a GPU allocation, also verify passthrough and the Slurm-assigned device selection with the intended CUDA framework.

## Primary references

- <https://pixi.prefix.dev/latest/>
- <https://pixi.prefix.dev/latest/integration/editor/jupyterlab/>
- <https://jupyter-server.readthedocs.io/en/latest/operators/security.html>
- <https://carpentries-incubator.github.io/pixi-introduction/>
- <https://atlas-software.docs.cern.ch/>
- <https://docs.unity.rc.umass.edu/documentation/>
- <https://usatlas.github.io/af-docs/containers/apptainer/usage/>
- <https://apptainer.org/docs/user/latest/gpu.html>
- <https://github.com/usatlas/af-benchmarking/blob/main/README.md>
- <https://slurm.schedmd.com/sbatch.html>
- <https://slurm.schedmd.com/job_exit_code.html>
