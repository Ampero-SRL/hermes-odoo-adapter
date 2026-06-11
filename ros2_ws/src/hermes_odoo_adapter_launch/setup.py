from glob import glob

from setuptools import setup

PACKAGE_NAME = "hermes_odoo_adapter_launch"

setup(
    name=PACKAGE_NAME,
    version="0.4.0",
    packages=[PACKAGE_NAME],
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + PACKAGE_NAME],
        ),
        ("share/" + PACKAGE_NAME, ["package.xml"]),
        ("share/" + PACKAGE_NAME + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Ampero S.r.l.",
    maintainer_email="tech@ampero.it",
    description=(
        "ament_python wrapper exposing the HERMES Odoo Adapter launch "
        "file via the ROS 2 package index."
    ),
    license="Apache-2.0",
    tests_require=["pytest"],
)
