# demos

Your own demos live here, one folder each — `demos/<name>/demo.py` and `scenes.py`.

Everything in this folder **except this README is gitignored**, so a demo of a private or
internal app never reaches the repository. That is the point of the folder: `examples/` is
for the templates that ship with the skill, and this is for your own work.

```
demos/<name>/demo.py      your config: TITLE, DEVICE, BUNDLE_ID, STREAMS, SCENES
demos/<name>/scenes.py    what happens, and which parts the viewer sees
exports/<name>/           what comes out: takes, then final/
```

Start by copying a template — they sit at the same depth as this folder, so the paths
inside them work unchanged, with nothing to edit:

```bash
cp -r examples/phone-hello demos/my-demo   # a phone demo on the simulator
cp -r examples/hello       demos/my-demo   # a web and terminal demo
rm demos/my-demo/run.sh                    # that is the smoke test's runner, not yours
```

Then point `OUT` at your own export folder, and edit the rest:

```python
OUT = Path("../../exports/my-demo")
```

These files are source you wrote, and nothing here is backed up by git. Treat
`exports/` as disposable; treat this folder as work.
