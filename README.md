# ATLAS Analysis on Unity

A growing guide to using UMass Unity as an analysis facility for ATLAS.

The first chapter, **Setting up the environment**, covers one-time creation of `/work/${USER_PI}/${USER}` and `/project/${USER_PI}/${USER}`, persistent `USER_PI` configuration, Slurm CPU/GPU allocations, CVMFS, an EL9 container through ATLASLocalRootBase and Apptainer, software selection, Bash shortcuts, and troubleshooting. `USER_PI` follows Unity's `pi_[PI's username]` convention, for example `pi_rclsa_umass_edu`. Later chapters assume those directory settings and interactive shortcuts are configured.

The second chapter, **Grid certificates and authentication**, covers obtaining a personal grid certificate, linking it to ATLAS IAM, installing an encrypted certificate/key pair on Unity, and creating a VOMS proxy with explicit input and output paths. It includes the optional `.bashrc` helper `atlas_proxy` for creation and atomic renewal, plus cleanup and troubleshooting. The rendered chapter is `grid-certificates/index.html`.

The third chapter, **Submitting jobs with Slurm**, explains worker-side environment setup and provides a self-contained PyROOT smoke test. Downloadable scripts are in `examples/slurm/`; the rendered chapter is `submitting-jobs/index.html`.

The fourth chapter, **Running on datasets with Slurm**, connects Rucio replication at NET2_LOCALGROUPDISK to direct XRootD reads in local Unity arrays, using a concrete `mc16_13TeV` SUSY15 dataset DID. It covers complete input manifests, worker proxies, per-file processing, bounded concurrency, validated results, retries, and merging. Downloadable helpers are in `examples/datasets/`; the rendered chapter is `running-on-datasets/index.html`.

The fifth chapter, **Using Pixi**, covers installation in the user area, persistent `PATH` configuration, personal tools with `pixi global`, and `pixi install` / `pixi run` for existing projects. It links to the Carpentries introduction for creating environments and adding packages. The rendered chapter is `using-pixi/index.html`.

The sixth chapter, **Using VS Code**, covers local SSH configuration, compute allocations, ordinary Remote SSH, a container RemoteCommand launcher, and Remote Tunnels started inside EL9. It includes Python Run/debug checks, notebook kernel selection, a remote Jupyter alternative, and session cleanup. Downloadable helpers and examples are in `examples/vscode/`; the rendered chapter is `using-vscode/index.html`.

The seventh chapter, **Using JupyterLab**, covers launching a notebook server from a Pixi project in a Slurm session, choosing Ubuntu or EL9, connecting a local browser through SSH, selecting and checking the kernel, and managing session lifetime. It reuses the environment and Pixi setup. The rendered chapter is `using-jupyterlab/index.html`.

The eighth chapter, **Codex Agents**, gives the full per-user workflow: start Codex inside EL9 with an ATLAS release, install isolated Rucio/AMI MCP clients, create a VOMS proxy, configure stdio servers, check authenticated access, and renew/resume sessions. It reuses the grid-certificate setup and assumes Pixi is installed as described in the earlier chapters. Downloadable configuration, a Pixi manifest, an environment launcher, and project instructions are in `examples/codex/`; the rendered chapter is `codex-agents/index.html`.

## Publish with GitHub Pages

In **Settings → Pages**, select **Deploy from a branch**, **main**, and **/ (root)**. Save. The expected project URL is <https://rafaellopesdesa.github.io/unity_atlas/> after Pages is enabled and its deployment finishes.

The rendered HTML, CSS, JavaScript, and `.nojekyll` are committed. No Jekyll theme, package installation, or custom build workflow is needed to serve this version. Pages activation is left to the repository owner.

## Edit and extend

1. Edit the Markdown sources in `docs/`.
2. For a new chapter, add its metadata to `docs/pages.json` in navigation order.
3. With Python 3.11 or newer and [Pandoc](https://pandoc.org/installing.html) installed, run `python3 tools/build_site.py` from any directory. The sources use Pandoc Markdown syntax.
4. Run `python3 tools/check_site.py`, `node --check assets/site.js`, and `bash -n examples/atlas-bashrc.sh`. For dataset and proxy helpers, also run `python3 -m unittest discover -s tests -v`; these tests exercise completeness, publication, and proxy renewal without grid credentials.
5. If editing examples displayed in full, update their matching code blocks in `docs/` too. The site checker verifies that these displayed examples match the downloads, checks Bash syntax, JSON, and TOML, and parses the Python examples.
6. Commit the sources **and** regenerated HTML/search index together.

Serve the repository root locally with `python3 -m http.server 8000`, then open <http://localhost:8000/>. The site also uses relative asset links so it works under the GitHub project subpath. `tools/template.html` and `assets/style.css` define the shared layout. All content and navigation remain readable without JavaScript; search, copy buttons, and the mobile menu are progressive enhancements.

## Report a problem

If an instruction does not work, [open an issue](https://github.com/rafaellopesdesa/unity_atlas/issues) with the page, command, error message, and compute-node hostname. Include the relevant software versions and whether you are on the Ubuntu host or inside EL9. Omit credentials, tokens, and private keys.

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
