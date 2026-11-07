UMass Unity provides the compute resources. CVMFS supplies the ATLAS software. An Enterprise Linux 9 container brings them together on Unity's Ubuntu hosts.

This guide documents how to use Unity as an analysis facility for ATLAS, from an interactive shell to a reproducible analysis environment.

::: {.start-panel}
## Start here

**[Setting up the environment →](setting-up-environment/)**

Request CPU or GPU resources, enter an EL9 container, and load the software needed for your analysis. Includes optional shell shortcuts and checks for common setup problems.
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

The first chapter covers interactive environment setup. Further chapters will cover data access and authentication, batch processing, analysis workflows, and notebooks and machine learning as those procedures are established.

The [Unity documentation](https://docs.unity.rc.umass.edu/documentation/) is the reference for cluster access, storage, and scheduling. The [ATLAS Software Documentation](https://atlas-software.docs.cern.ch/) is the reference for ATLAS software and analysis procedures.

::: {.callout}
**Initial version.** These instructions combine the documented Unity and ATLAS interfaces. End-to-end validation on Unity's newly installed CVMFS service is still pending. The first chapter includes checks to run on an allocated compute node.
:::

Found a problem or tested a setup? [Open an issue](https://github.com/rafaellopesdesa/unity_atlas/issues) with the relevant command, error, and compute-node hostname. Omit credentials and tokens.
