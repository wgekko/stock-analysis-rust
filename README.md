# stock-analysis-rust
analisis de acciones usando rust para el calculo

es una app que aplica concepto de análisis técnico para determinar estrategias 
de potenciales comprar o ventas de activos 
esta creado a fines didácticos para buscar aplicar el concepto de interacción 
entre python y rust. Buscando la optimización de tiempos de respuesta de las consultas

la estructura del proyecto es

STOCK-ANALYSIS-RUST

1-.STREAMLIT
-------config.toml
2---PAGES
------1-ARCHIVO
------2-ARCHIVO
------3-ARCHIVO
3---RUST_ENGINE
-----SRC
---------LIB.RS
-----TARGET
---------MATURIN
---------RELEASE
---------WHEELS
---------CARGO.LOCK
.........CARGO.TOML
---------PYPROJECT.TOML
4---APP.PY
5--REQUIMENTS.TXT

IMPORTANTE ESTOS COMANDO ESTA PENSADOS SI SE TRABAJA DESDE LINUX 
USANDO LA TERMINAL 

dentro de la carpeta rust_engine  se debe escribir estos comandos

rust_engine$ maturin build --release

una vez que termino el proceso exitoso 
se debe escrbir 

pip install --user target/wheels/oscilador-0.1.0-cp312-cp312-manylinux_2_34_x86_64.whl --break-system-packages --force-reinstall



luego para ejecutar la app se debe correr en al terminal dentro del proyecto 
el comando 
streamlit run app.py
