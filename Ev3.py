import sys
import re
import csv
from datetime import datetime, date, timedelta
from pathlib import Path
import sqlite3

# Configuración
DB_FILE = Path("reservaciones.db")
EXPORT_DIR = Path("ARCHIVOS PY")

TURNOS = ["Matutino", "Vespertino", "Nocturno"]


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            clave INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            apellidos TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS salas (
            clave INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            cupo INTEGER NOT NULL CHECK(cupo > 0)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reservaciones (
            folio INTEGER PRIMARY KEY,
            clave_cliente INTEGER NOT NULL,
            clave_sala INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            turno TEXT NOT NULL,
            nombre_evento TEXT NOT NULL,
            FOREIGN KEY (clave_cliente) REFERENCES clientes(clave),
            FOREIGN KEY (clave_sala) REFERENCES salas(clave),
            UNIQUE(clave_sala, fecha, turno)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contadores (
            nombre TEXT PRIMARY KEY,
            valor INTEGER NOT NULL
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO contadores (nombre, valor) VALUES ('cliente', 1)")
    cursor.execute("INSERT OR IGNORE INTO contadores (nombre, valor) VALUES ('sala', 1)")
    cursor.execute("INSERT OR IGNORE INTO contadores (nombre, valor) VALUES ('folio', 1)")
    conn.commit()
    conn.close()


def obtener_siguiente_valor(nombre):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT valor FROM contadores WHERE nombre = ?", (nombre,))
    valor = cursor.fetchone()[0]
    conn.close()
    return valor


def incrementar_contador(nombre):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE contadores SET valor = valor + 1 WHERE nombre = ?", (nombre,))
    conn.commit()
    conn.close()


def fecha_str_a_date(fecha_str):
    return datetime.strptime(fecha_str, "%d/%m/%Y").date()


def date_a_fecha_str(fecha_obj):
    return fecha_obj.strftime("%d/%m/%Y")


def es_domingo(fecha):
    return fecha.weekday() == 6


def pausa():
    input("\nPresione Enter para continuar...")


def validar_texto_letras_y_espacios(texto):
    patron = r"[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+"
    return bool(re.fullmatch(patron, texto.strip()))


def validar_no_vacio(texto):
    return bool(texto.strip())


def mostrar_clientes_ordenados():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT clave, nombre, apellidos FROM clientes ORDER BY apellidos, nombre")
    clientes = cursor.fetchall()
    conn.close()

    if not clientes:
        print("No hay clientes registrados.")
        return None

    print("\nClientes registrados:")
    print("=" * 60)
    for clave, nombre, apellidos in clientes:
        print(f"Clave: {clave:>3} | Apellidos: {apellidos:<20} | Nombre: {nombre:<20}")
    print("=" * 60)
    return [c[0] for c in clientes]


def seleccionar_cliente():
    while True:
        claves_validas = mostrar_clientes_ordenados()
        if claves_validas is None:
            return None
        entrada = input("\nIngrese la clave del cliente (o 'CANCELAR'): ").strip()
        if entrada.upper() == "CANCELAR":
            return None
        try:
            clave = int(entrada)
            if clave in claves_validas:
                return clave
            else:
                print("Clave inválida.")
        except ValueError:
            print("Entrada inválida.")


def solicitar_fecha_reservacion():
    hoy = date.today()
    fecha_minima = hoy + timedelta(days=2)
    while True:
        entrada = input(f"Ingrese la fecha de la reservación (dd/mm/yyyy). Mínimo {date_a_fecha_str(fecha_minima)}: ").strip()
        try:
            fecha = fecha_str_a_date(entrada)
        except ValueError:
            print("Formato de fecha inválido. Use dd/mm/yyyy.")
            continue

        if fecha < fecha_minima:
            print(f"La fecha debe ser al menos {date_a_fecha_str(fecha_minima)}.")
            continue

        if es_domingo(fecha):
            print("No se permiten reservaciones en domingos.")
            sugerida = fecha + timedelta(days=1)
            print(f"¿Desea usar la fecha sugerida: {date_a_fecha_str(sugerida)}? (S/N)")
            if input().strip().upper() == "S":
                return sugerida
            else:
                continue

        return fecha


def obtener_salas_disponibles_en_fecha(fecha):
    fecha_str = date_a_fecha_str(fecha)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT clave, nombre, cupo FROM salas")
    todas_salas = cursor.fetchall()

    cursor.execute("SELECT clave_sala, turno FROM reservaciones WHERE fecha = ?", (fecha_str,))
    ocupadas = set(cursor.fetchall())
    conn.close()

    disponibles = []
    for clave, nombre, cupo in todas_salas:
        turnos_libres = [t for t in TURNOS if (clave, t) not in ocupadas]
        if turnos_libres:
            disponibles.append({"clave": clave, "nombre": nombre, "cupo": cupo, "turnos_libres": turnos_libres})
    return disponibles


def seleccionar_sala_y_turno(fecha):
    disponibles = obtener_salas_disponibles_en_fecha(fecha)
    if not disponibles:
        print("No hay salas disponibles en la fecha seleccionada.")
        return None, None

    print("\nSalas disponibles:")
    print("=" * 80)
    for s in disponibles:
        print(f"Clave: {s['clave']:>3} | Nombre: {s['nombre']:<25} | Cupo: {s['cupo']:>4} | Turnos: {', '.join(s['turnos_libres'])}")
    print("=" * 80)

    while True:
        entrada = input("\nClave de sala (o 'CANCELAR'): ").strip()
        if entrada.upper() == "CANCELAR":
            return None, None
        try:
            clave = int(entrada)
        except ValueError:
            print("Entrada no válida.")
            continue

        sala = next((s for s in disponibles if s["clave"] == clave), None)
        if not sala:
            print("Clave de sala inválida.")
            continue

        while True:
            turno_input = input(f"Turno ({', '.join(sala['turnos_libres'])}) o 'CANCELAR': ").strip()
            if turno_input.upper() == "CANCELAR":
                return None, None
            turno = turno_input.capitalize()
            if turno in sala["turnos_libres"]:
                return clave, turno
            else:
                print("Turno inválido o no disponible.")


def registrar_reservacion():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM salas")
    if cursor.fetchone()[0] == 0:
        conn.close()
        print("No hay salas registradas. Registre al menos una sala antes de continuar.")
        pausa()
        return

    clave_cliente = seleccionar_cliente()
    if clave_cliente is None:
        print("Operación cancelada.")
        pausa()
        return

    fecha = solicitar_fecha_reservacion()
    clave_sala, turno = seleccionar_sala_y_turno(fecha)
    if clave_sala is None:
        print("Operación cancelada.")
        pausa()
        return

    while True:
        nombre_evento = input("Nombre del evento: ").strip()
        if validar_no_vacio(nombre_evento):
            break
        print("El nombre del evento no debe estar vacío.")

    folio = obtener_siguiente_valor("folio")
    fecha_str = date_a_fecha_str(fecha)
    try:
        cursor.execute("""
            INSERT INTO reservaciones (folio, clave_cliente, clave_sala, fecha, turno, nombre_evento)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (folio, clave_cliente, clave_sala, fecha_str, turno, nombre_evento))
        conn.commit()
        incrementar_contador("folio")
        print(f"Reservación creada. Folio: {folio}")
    except sqlite3.IntegrityError:
        print("Error: conflicto de disponibilidad (no debería ocurrir).")
    finally:
        conn.close()
    pausa()


def obtener_rango_fechas():
    while True:
        try:
            inicio = fecha_str_a_date(input("Fecha de inicio (dd/mm/yyyy): ").strip())
            fin = fecha_str_a_date(input("Fecha de fin (dd/mm/yyyy): ").strip())
            if inicio <= fin:
                return inicio, fin
            else:
                print("La fecha de inicio debe ser menor o igual a la fecha fin.")
        except ValueError:
            print("Formato inválido. Use dd/mm/yyyy.")


def editar_nombre_evento():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM reservaciones")
    if cursor.fetchone()[0] == 0:
        conn.close()
        print("No hay reservaciones.")
        pausa()
        return

    inicio, fin = obtener_rango_fechas()
    inicio_str = date_a_fecha_str(inicio)
    fin_str = date_a_fecha_str(fin)

    cursor.execute("""
        SELECT r.folio, r.nombre_evento, r.fecha, s.nombre, c.nombre, c.apellidos
        FROM reservaciones r
        JOIN salas s ON r.clave_sala = s.clave
        JOIN clientes c ON r.clave_cliente = c.clave
        WHERE r.fecha BETWEEN ? AND ?
        ORDER BY r.fecha, r.folio
    """, (inicio_str, fin_str))

    resultados = cursor.fetchall()
    if not resultados:
        conn.close()
        print("No hay reservaciones en el rango.")
        pausa()
        return

    print("\n" + "=" * 100)
    titulo = f"Reservaciones entre {inicio_str} y {fin_str}"
    print(titulo.center(100))
    print("=" * 100)
    print(f"{'Folio':^8}{'Fecha':^12}{'Sala':^20}{'Cliente':^30}{'Evento':^30}")
    print("-" * 100)
    folios_validos = set()
    for folio, evento, fecha, sala, nom, ap in resultados:
        cliente = f"{nom} {ap}"
        print(f"{folio:^8}{fecha:^12}{sala[:20]:^20}{cliente[:30]:^30}{evento[:30]:^30}")
        folios_validos.add(folio)
    print("=" * 100)

    while True:
        entrada = input("\nFolio a editar (o 'CANCELAR'): ").strip()
        if entrada.upper() == "CANCELAR":
            print("Operación cancelada.")
            break
        try:
            folio_editar = int(entrada)
        except ValueError:
            print("Entrada inválida.")
            continue
        if folio_editar in folios_validos:
            while True:
                nuevo_nombre = input("Nuevo nombre del evento: ").strip()
                if validar_no_vacio(nuevo_nombre):
                    cursor.execute("UPDATE reservaciones SET nombre_evento = ? WHERE folio = ?", (nuevo_nombre, folio_editar))
                    conn.commit()
                    print("Nombre del evento actualizado.")
                    break
                else:
                    print("Nombre no válido.")
            break
        else:
            print("Folio no válido en el rango.")
    conn.close()
    pausa()


def consultar_reservaciones_por_fecha():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM reservaciones")
    if cursor.fetchone()[0] == 0:
        conn.close()
        print("No hay reservaciones registradas.")
        pausa()
        return

    entrada = input("Fecha a consultar (dd/mm/yyyy) [Enter para hoy]: ").strip()
    if not entrada:
        fecha_consulta = date.today()
    else:
        try:
            fecha_consulta = fecha_str_a_date(entrada)
        except ValueError:
            print("Formato inválido.")
            conn.close()
            pausa()
            return

    fecha_str = date_a_fecha_str(fecha_consulta)
    cursor.execute("""
        SELECT r.folio, r.fecha, s.nombre, c.nombre, c.apellidos, r.turno, r.nombre_evento
        FROM reservaciones r
        JOIN salas s ON r.clave_sala = s.clave
        JOIN clientes c ON r.clave_cliente = c.clave
        WHERE r.fecha = ?
        ORDER BY r.turno
    """, (fecha_str,))

    resultados = cursor.fetchall()
    conn.close()

    if not resultados:
        print(f"No hay reservaciones para el {fecha_str}.")
        pausa()
        return

    print("\n" + "=" * 100)
    titulo = f"REPORTE DE RESERVACIONES DEL {fecha_str}"
    print(titulo.center(100))
    print("=" * 100)
    print(f"{'Folio':^8}{'Fecha':^12}{'Sala':^20}{'Cliente':^25}{'Turno':^12}{'Evento':^25}")
    print("-" * 100)
    lista_resultados = []
    for folio, fecha, sala, nom, ap, turno, evento in resultados:
        cliente = f"{nom} {ap}"
        print(f"{folio:^8}{fecha:^12}{sala[:20]:^20}{cliente[:25]:^25}{turno[:12]:^12}{evento[:25]:^25}")
        lista_resultados.append({
            "folio": folio,
            "fecha": fecha,
            "sala": sala,
            "cliente": cliente,
            "turno": turno,
            "evento": evento
        })
    print("=" * 100)

    while True:
        print("\nOpciones de exportación:")
        print("1. Exportar a CSV")
        print("2. No exportar")
        opcion = input("Seleccione una opción: ").strip()
        if opcion == "1":
            exportar_csv(lista_resultados, fecha_consulta)
            break
        elif opcion == "2":
            break
        else:
            print("Opción inválida.")
    pausa()


def exportar_csv(lista_resultados, fecha_consulta):
    try:
        EXPORT_DIR.mkdir(exist_ok=True)
    except Exception as e:
        print(f"Error al crear el directorio de exportación '{EXPORT_DIR}': {e}")
        return

    nombre_archivo = f"reporte_reservaciones_{date_a_fecha_str(fecha_consulta).replace('/', '-')}.csv"
    ruta = EXPORT_DIR / nombre_archivo

    try:
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            campos = ["folio", "fecha", "sala", "cliente", "turno", "evento"]
            escritor = csv.DictWriter(f, fieldnames=campos)
            escritor.writeheader()
            for fila in lista_resultados:
                escritor.writerow(fila)
        print(f"Reporte exportado a CSV: {ruta}")
    except Exception as e:
        print(f"Error al exportar CSV: {e}")


def registrar_cliente():
    print("\n--- Registrar Nuevo Cliente ---")
    while True:
        nombre = input("Nombre(s): ").strip()
        if validar_texto_letras_y_espacios(nombre):
            break
        print("Nombre inválido. Solo letras y espacios.")

    while True:
        apellidos = input("Apellidos: ").strip()
        if validar_texto_letras_y_espacios(apellidos):
            break
        print("Apellidos inválidos. Solo letras y espacios.")

    clave = obtener_siguiente_valor("cliente")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO clientes (clave, nombre, apellidos) VALUES (?, ?, ?)",
                   (clave, nombre.title(), apellidos.title()))
    conn.commit()
    conn.close()
    incrementar_contador("cliente")
    print(f"Cliente registrado. Clave: {clave}")
    pausa()


def registrar_sala():
    print("\n--- Registrar Nueva Sala ---")
    while True:
        nombre = input("Nombre de la sala: ").strip()
        if validar_no_vacio(nombre):
            break
        print("El nombre de la sala no debe estar vacío.")

    while True:
        cupo_str = input("Cupo máximo: ").strip()
        try:
            cupo = int(cupo_str)
            if cupo > 0:
                break
            print("El cupo debe ser un número entero positivo.")
        except ValueError:
            print("Entrada inválida. Debe ser un número.")

    clave = obtener_siguiente_valor("sala")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO salas (clave, nombre, cupo) VALUES (?, ?, ?)",
                   (clave, nombre.title(), cupo))
    conn.commit()
    conn.close()
    incrementar_contador("sala")
    print(f"Sala registrada. Clave: {clave}")
    pausa()


def confirmar_salida():
    while True:
        confirmacion = input("¿Está seguro que desea salir? (S/N): ").strip().upper()
        if confirmacion == "S":
            return True
        elif confirmacion == "N":
            return False
        else:
            print("Opción inválida. Ingrese S o N.")


def mostrar_menu():
    print("\n" + "=" * 40)
    print("  Sistema de Gestión de Reservaciones")
    print("=" * 40)
    print("1. Registrar Cliente")
    print("2. Registrar Sala")
    print("3. Registrar Reservación")
    print("4. Editar Nombre de Evento")
    print("5. Consultar Reservaciones por Fecha (Exportar a CSV)")
    print("6. Salir")
    print("=" * 40)


def main():
    init_db()
    while True:
        mostrar_menu()
        opcion = input("Seleccione una opción: ").strip()
        if opcion == "1":
            registrar_cliente()
        elif opcion == "2":
            registrar_sala()
        elif opcion == "3":
            registrar_reservacion()
        elif opcion == "4":
            editar_nombre_evento()
        elif opcion == "5":
            consultar_reservaciones_por_fecha()
        elif opcion == "6":
            if confirmar_salida():
                print("Saliendo del sistema.")
                sys.exit(0)
            else:
                continue
        else:
            print("Opción no válida. Intente de nuevo.")
            pausa()


if __name__ == "__main__":
    main()