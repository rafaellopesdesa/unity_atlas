UMass Unity provides the compute resources. CVMFS supplies the ATLAS software. An Enterprise Linux 9 container brings them together on Unity's Ubuntu hosts.

This guide documents how to use Unity as an analysis facility for ATLAS, from an interactive shell to a reproducible analysis environment.

::: {.start-panel}
## Start here

**[Setting up the environment →](setting-up-environment/)**

Create your work/project directories once, save `USER_PI` and the shell shortcuts, request CPU or GPU resources, enter an EL9 container, and load the software needed for your analysis.

**[Submitting jobs with Slurm →](submitting-jobs/)**

Turn the tested interactive environment into a batch job. Includes downloadable scripts, a PyROOT smoke test, resource requests, logs, and troubleshooting.

**[Using VS Code →](using-vscode/)**

Connect to an allocated node, start a VS Code backend inside EL9, and configure integrated ATLAS Python execution, debugging, and notebook kernels. Includes SSH and tunnel methods.

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
| Your work directory | Keep analysis code, builds, inputs, and outputs on writable Unity storage. |

Start the container **after** the allocation has started. The container runs within that allocation; it does not reserve additional resources.

## About this guide

The first four chapters cover interactive environment setup, Slurm batch jobs, VS Code, and Codex with authenticated catalog access. Further chapters will cover data movement, analysis workflows, and machine learning as those procedures are established.

The [Unity documentation](https://docs.unity.rc.umass.edu/documentation/) is the reference for cluster access, storage, and scheduling. The [ATLAS Software Documentation](https://atlas-software.docs.cern.ch/) is the reference for ATLAS software and analysis procedures.

::: {.callout}
**Validation status.** Rafael has tested the interactive environment recipe successfully on Unity, including access to `/work` without an explicit mount and `nvidia-smi` inside EL9 when launching with explicit `--nv`. The batch, VS Code, and Codex recipes have passed local checks and await end-to-end Unity tests; the Codex chapter lists the required authenticated checks.
:::

Found a problem or tested a setup? [Open an issue](https://github.com/rafaellopesdesa/unity_atlas/issues) with the relevant command, error, and compute-node hostname. Omit credentials and tokens.
