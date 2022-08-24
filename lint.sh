set -x

black package_statistics.py
flake8 package_statistics.py --max-line-length=100
pylama package_statistics.py 
mypy package_statistics.py 