"""services — Servicios desacoplados de la interfaz (App queda como coordinador).

Cada servicio encapsula una responsabilidad que antes vivia acoplada a la
clase god-object App en audioclass_v91.py: motores de transcripcion, grabacion,
microfono y actualizaciones. App los instancia y delega, en lugar de heredar
toda la logica.
"""
