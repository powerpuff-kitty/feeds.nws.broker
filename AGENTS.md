# Feed directory instructions

- Read [MAINTENANCE.md](MAINTENANCE.md) for data provenance, generation and refresh commands.
- Treat `README.md` and `directory/` as generated outputs. Edit `scripts/build_directory.py` for presentation or output changes.
- Use the public nws.broker catalogue and subscription endpoints as inputs. Keep publisher feed contents and private configuration outside this repository.
- Run `python3 -m unittest discover -s tests -v` and `git diff --check` before publishing.
