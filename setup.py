import os
import sys
from setuptools import setup, find_packages
from tethys_apps.app_installation import custom_develop_command, custom_install_command

### Apps Definition ###
app_package = 'hydrotop'
release_package = 'tethysapp-' + app_package
app_class = 'hydrotop.app:Hydrotop'
app_package_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tethysapp', app_package)

### Python Dependencies ###
dependencies = []

setup(
    name=release_package,
    version='1.0.0',
    tags='"Hydrology", "topkapi", "topnet", "terrain analysis", "TauDEM", "watershed delineation", "hydrotop", "modeling", "reference ET", "evapotranspiration", "daymet", "climate files", "forcing files", "ssurgo", "soil files", "saturated hydraulic conductivity", "porosity", "residual soil moisture content", "gssurgo", "terrain analysis", "bubbling pressure", "pore size distribution","USU", "UWRL", "Utah State University", "hydroshare"',
    description='Model instance for TOPKAPI, model input for TOPNET, and downloading hydrologic ataset',
    long_description='',
    keywords='',
    author='Prasanna',
    author_email='dahal.prasanna@gmail.com',
    url='',
    license='',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    namespace_packages=['tethysapp', 'tethysapp.' + app_package],
    include_package_data=True,
    zip_safe=False,
    install_requires=dependencies,
    cmdclass={
        'install': custom_install_command(app_package, app_package_dir, dependencies),
        'develop': custom_develop_command(app_package, app_package_dir, dependencies)
    }
)
