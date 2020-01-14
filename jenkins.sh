#!/bin/bash
# Run tests in Jenkins environment.

pip install -e .[dev]

# Build distro images.
python setup.py --command-packages=stdeb3.command bdist_deb
rm ./*.tar.gz
python setup.py bdist_wheel
mkdir -p build/
VERSION=$(python setup.py --version)
echo "${VERSION}" > ./VERSION
sed\
 -e "s/VERSION/${VERSION}/g"\
 -e "s/BRANCH/${BRANCH}/g"\
  artifactory.json > build/artifactory.json
