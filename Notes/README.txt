To install setup.cfg install_requires:
pip install -e .  

To update requirements.txt:
pip freeze > requirements.txt

pyemvue upgrade:
pip install --upgrade pyemvue

To install evbilling with locally patched pyemvue:
pipx install evbilling-1.2.0-py3-none-any.whl
pipx inject evbilling ./pyemvue-0.18.8.1-py3-none-any.whl --force

Note: ocrbev1.auto_geometry() (Deleted in v2.0.0): Missing raise LookupError if
Service Information block not found.

Notes:
- Bill files ignored beginning v1.4.3.
- evchargers.download_usage_data() converted to use merged channels in v1.1.0.
