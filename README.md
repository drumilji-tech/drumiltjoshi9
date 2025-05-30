# iSight

An application to automatically identify issues in Wind and Solar (renewables) technologies.


## Protocol for Making an Executable Version (EXE)

1. Set the value of the `CURRENT_ENV` variable in config.py to one of the valid keys of `ENVIRONMENTS`
2. Increment the version of the app in the iSIghtSolar.spec
3. Run the script to produce the exe:

```bash
% pyinstaller iSightSolar.spec
```

Upon successful completion, it will appear in the dist/ folder of the repo.

## Tests

To run tests for the Solar side of the application, run:

```bash
python -m pytest Tests/Solar/
```
