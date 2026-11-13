UMass Unity provides the compute resources. CVMFS supplies the ATLAS software, and an Enterprise Linux 9 container provides the runtime for ATLAS releases on Unity's Ubuntu hosts. Pixi manages project dependencies and personal tools.

This guide documents how to use Unity as an analysis facility for ATLAS, from an interactive shell to a reproducible analysis environment.

::: {.start-panel}
## Start here

**[Setting up the environment →](setting-up-environment/)**

Create your work/project directories once, save `USER_PI` and the shell shortcuts, request CPU or GPU resources, enter an EL9 container, and load the software needed for your analysis.

**[Grid certificates and authentication →](grid-certificates/)**

Obtain and register a personal grid certificate, install its encrypted private key on Unity, and create a short-lived ATLAS proxy. Includes renewal and troubleshooting for credential and output-path errors.

**[Submitting jobs with Slurm →](submitting-jobs/)**

Turn the interactive environment into a batch job. Includes downloadable scripts, a PyROOT smoke test, resource requests, logs, and troubleshooting.

**[Using Pixi →](using-pixi/)**

Install Pixi in your user area, manage personal command-line tools with `pixi global`, and use `pixi install` and `pixi run` with an existing project's environment.

**[Using VS Code →](using-vscode/)**

Connect to an allocated node, start a VS Code backend inside EL9, and configure integrated ATLAS Python execution, debugging, and notebook kernels. Includes SSH and tunnel methods.

**[Using JupyterLab →](using-jupyterlab/)**

Start a Pixi-based notebook server in your own Slurm session, optionally inside EL9, and connect from your browser through an SSH tunnel. Check the kernel, save notebooks on Unity, and reconnect or finish the session.

**[Codex Agents →](codex-agents/)**

Run Codex with your ATLAS release inside EL9. Install personal Rucio and AMI MCP servers, authenticate with a grid proxy, and connect them to the agent for dataset discovery and metadata queries.
:::

## How the environment fits together

| Component | Its role |
| --- | --- |
| Unity login node | Connect, edit files, and request resources. |
| Slurm allocation | Reserve CPUs, memory, time, and optional GPUs on a compute node. |
| Apptainer container | Provide the EL9 userspace required by the ATLAS release. |
| CVMFS | Deliver centrally maintained software and container images. |
| Grid proxy | Authenticate to ATLAS grid services using your registered certificate identity and VO attributes. |
| Pixi environment | Supply a project's own packages and command-line tools. |
| Your work directory | Keep analysis code, builds, inputs, and outputs on writable Unity storage. |

Start the container **after** the allocation has started. The container runs within that allocation; it does not reserve additional resources. A self-contained Pixi project that supports Ubuntu can also run directly on the allocated host, as described in the Pixi and JupyterLab chapters.

The environment chapter defines the directory settings and shell helpers used throughout this guide. The grid-certificate chapter prepares the identity and proxy used for authenticated grid access, including the Codex MCP servers. The Pixi chapter supplies the package-management basics used by JupyterLab and Codex. Choose VS Code, JupyterLab, or Codex according to how you want to work; you do not need to start all three.

## About this guide

The chapters cover interactive environment setup, grid certificates and authentication, Slurm batch jobs, Pixi, VS Code, JupyterLab, and Codex with authenticated catalog access. Further chapters will cover data movement, analysis workflows, and machine learning as those procedures are established.

The [Unity documentation](https://docs.unity.rc.umass.edu/documentation/) is the reference for cluster access, storage, and scheduling. The [ATLAS Software Documentation](https://atlas-software.docs.cern.ch/) is the reference for ATLAS software and analysis procedures.

If an instruction does not work, [open an issue](https://github.com/rafaellopesdesa/unity_atlas/issues) with the page, command, error message, and compute-node hostname. Include the relevant software versions and whether you are on the Ubuntu host or inside EL9. Omit credentials, tokens, and private keys.
