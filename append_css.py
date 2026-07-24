css = """
input[type="text"], input[type="file"], textarea {
  width: 100%;
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-main);
  font-family: 'Inter', sans-serif;
  font-size: 14px;
  transition: var(--transition-smooth);
}

input[type="text"]:focus, textarea:focus {
  outline: none;
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: var(--text-muted);
  font-size: 14px;
}

.input-group {
  margin-bottom: 20px;
}
"""
with open("frontend/src/app/globals.css", "a") as f:
    f.write(css)
