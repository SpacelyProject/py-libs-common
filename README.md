# py-libs-common

Repository dedicated to various common libraries shared across projects to promote reuse.


# Useful tips for reorganizing libraries.

Each library comes with a pyproject.toml file, which specifies how to build that project in as a Python package. 

Among other things, the pyproject.toml specifies a library name <NAME>.

In order for the library to compile correctly, you need to make sure that there is an __init__.py file which is findable in a subdirectory called <NAME> or /src/<NAME>.

For example, the fnal_libIO package lives in /libIO/fnal_libIO/, and /libIO/pyproject.toml specifies the project name as "fnal_libIO".