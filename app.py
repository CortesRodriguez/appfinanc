"""Punto de entrada de la aplicacion (Vista de Desarrollo / Capa de Presentacion)."""

from src.web import create_app

app = create_app()

if __name__ == "__main__":
     app.run(debug=True, port=5001) 
