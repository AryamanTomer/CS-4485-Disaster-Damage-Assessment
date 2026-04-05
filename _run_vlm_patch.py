from pathlib import Path
path = Path("frontend/src/App.jsx")
text = path.read_text(encoding="utf-8")
old_state = """  const [mapSearchTarget, setMapSearchTarget] = useState(null);\n  const mapSearchAbortRef = useRef(null);"""
new_state = """  const [mapSearchTarget, setMapSearchTarget] = useState(null);\n  const mapSearchAbortRef = useRef(null);\n  const [vlmPostName, setVlmPostName] = useState('');\n  const [vlmMode, setVlmMode] = useState('crops');\n  const [vlmLoading, setVlmLoading] = useState(false);\n  const [vlmError, setVlmError] = useState(null);\n  const [vlmResult, setVlmResult] = useState(null);"""
if old_state not in text: raise SystemExit("state")
text = text.replace(old_state, new_state, 1)
anchor = """    loadTilePredictions();\n  }, []);\n\n  useEffect(() => {\n    const loadTransformsFromLabels = async () => {"""
insert = open("_vlm_insert.txt", encoding="utf-8").read()
if anchor not in text: raise SystemExit("anchor2")
text = text.replace(anchor, insert, 1)
panel = """              <div className=\"damage-legend-overlay\" role=\"note\" aria-label=\"Damage class legend\">"""
panel_ins = open("_vlm_panel.txt", encoding="utf-8").read()
if panel not in text: raise SystemExit("panel")
text = text.replace(panel, panel_ins, 1)
path.write_text(text, encoding="utf-8")
print("ok")
