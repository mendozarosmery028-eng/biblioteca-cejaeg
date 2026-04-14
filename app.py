from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import date, timedelta
import sqlite3, hashlib, os

app = Flask(__name__)
app.secret_key = 'biblioteca_escolar_2024_cambia_esto'
DB = 'biblioteca.db'

# ── helpers ──────────────────────────────────────────────────────────────────

def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        if session['user'].get('rol') != 'admin':
            flash('Acceso restringido: solo administradores')
            return redirect(url_for('inicio'))
        return f(*args, **kwargs)
    return decorated

# ── init db ──────────────────────────────────────────────────────────────────

def init_db():
    con = get_db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        usuario TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        rol TEXT DEFAULT 'encargado'
    );

    CREATE TABLE IF NOT EXISTS titulos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        autor TEXT NOT NULL,
        categoria TEXT,
        isbn TEXT,
        anio INTEGER,
        creado TEXT DEFAULT (date('now'))
    );

    CREATE TABLE IF NOT EXISTS ejemplares (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo_id INTEGER NOT NULL REFERENCES titulos(id) ON DELETE CASCADE,
        numero INTEGER NOT NULL,
        estado TEXT DEFAULT 'disponible',
        nota TEXT
    );

    CREATE TABLE IF NOT EXISTS prestamos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ejemplar_id INTEGER NOT NULL REFERENCES ejemplares(id),
        alumno TEXT NOT NULL,
        grado TEXT,
        inicio TEXT NOT NULL,
        fin TEXT NOT NULL,
        devuelto TEXT,
        creado_por TEXT,
        nota TEXT
    );

    CREATE TABLE IF NOT EXISTS donaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donante TEXT NOT NULL,
        titulo_id INTEGER REFERENCES titulos(id),
        cantidad INTEGER DEFAULT 1,
        fecha TEXT NOT NULL,
        nota TEXT
    );
    """)

    # admin por defecto
    cur = con.execute("SELECT id FROM usuarios WHERE usuario='admin'")
    if not cur.fetchone():
        con.execute("INSERT INTO usuarios (nombre,usuario,password,rol) VALUES (?,?,?,?)",
                    ('Administrador','admin', hash_pw('admin123'), 'admin'))

    # 6 encargados por defecto
    encargados = [
        ('Encargado 1', 'encargado1', 'encargado123'),
        ('Encargado 2', 'encargado2', 'encargado123'),
        ('Encargado 3', 'encargado3', 'encargado123'),
        ('Encargado 4', 'encargado4', 'encargado123'),
        ('Encargado 5', 'encargado5', 'encargado123'),
        ('Encargado 6', 'encargado6', 'encargado123'),
    ]
    for nombre, usuario, pw in encargados:
        cur = con.execute("SELECT id FROM usuarios WHERE usuario=?", (usuario,))
        if not cur.fetchone():
            con.execute("INSERT INTO usuarios (nombre,usuario,password,rol) VALUES (?,?,?,?)",
                        (nombre, usuario, hash_pw(pw), 'encargado'))

    con.commit()
    con.close()

# ── auth ─────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form['usuario']
        p = hash_pw(request.form['password'])
        con = get_db()
        row = con.execute("SELECT * FROM usuarios WHERE usuario=? AND password=?", (u,p)).fetchone()
        con.close()
        if row:
            session['user'] = dict(row)
            return redirect(url_for('inicio'))
        flash('Usuario o contraseña incorrectos')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── inicio ────────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def inicio():
    con = get_db()
    hoy = date.today().isoformat()
    tres_dias = (date.today() + timedelta(days=3)).isoformat()

    stats = {
        'titulos': con.execute("SELECT COUNT(*) FROM titulos").fetchone()[0],
        'ejemplares': con.execute("SELECT COUNT(*) FROM ejemplares").fetchone()[0],
        'prestados': con.execute("SELECT COUNT(*) FROM ejemplares WHERE estado='prestado'").fetchone()[0],
        'disponibles': con.execute("SELECT COUNT(*) FROM ejemplares WHERE estado='disponible'").fetchone()[0],
        'vencidos': con.execute("SELECT COUNT(*) FROM prestamos WHERE devuelto IS NULL AND fin < ?", (hoy,)).fetchone()[0],
        'devolver_hoy': con.execute("SELECT COUNT(*) FROM prestamos WHERE devuelto IS NULL AND fin = ?", (hoy,)).fetchone()[0],
    }

    vencen_hoy = con.execute("""
        SELECT p.*, e.numero, t.titulo, t.autor
        FROM prestamos p
        JOIN ejemplares e ON e.id = p.ejemplar_id
        JOIN titulos t ON t.id = e.titulo_id
        WHERE p.devuelto IS NULL AND p.fin = ?
        ORDER BY p.alumno
    """, (hoy,)).fetchall()

    vencidos = con.execute("""
        SELECT p.*, e.numero, t.titulo, t.autor,
               julianday('now') - julianday(p.fin) AS dias_vencido
        FROM prestamos p
        JOIN ejemplares e ON e.id = p.ejemplar_id
        JOIN titulos t ON t.id = e.titulo_id
        WHERE p.devuelto IS NULL AND p.fin < ?
        ORDER BY p.fin ASC
    """, (hoy,)).fetchall()

    por_vencer = con.execute("""
        SELECT p.*, e.numero, t.titulo, t.autor
        FROM prestamos p
        JOIN ejemplares e ON e.id = p.ejemplar_id
        JOIN titulos t ON t.id = e.titulo_id
        WHERE p.devuelto IS NULL AND p.fin > ? AND p.fin <= ?
        ORDER BY p.fin ASC
    """, (hoy, tres_dias)).fetchall()

    recientes = con.execute("""
        SELECT p.*, e.numero, t.titulo
        FROM prestamos p
        JOIN ejemplares e ON e.id = p.ejemplar_id
        JOIN titulos t ON t.id = e.titulo_id
        WHERE p.devuelto IS NULL
        ORDER BY p.id DESC LIMIT 8
    """).fetchall()

    con.close()
    return render_template('inicio.html', stats=stats, vencen_hoy=vencen_hoy,
                           vencidos=vencidos, por_vencer=por_vencer, recientes=recientes, hoy=hoy)

# ── libros / títulos ─────────────────────────────────────────────────────────

@app.route('/libros')
@login_required
def libros():
    q = request.args.get('q','')
    cat = request.args.get('cat','')
    con = get_db()
    sql = """
        SELECT t.*,
               COUNT(e.id) AS total_ejemplares,
               SUM(CASE WHEN e.estado='disponible' THEN 1 ELSE 0 END) AS disponibles,
               SUM(CASE WHEN e.estado='prestado' THEN 1 ELSE 0 END) AS prestados
        FROM titulos t
        LEFT JOIN ejemplares e ON e.titulo_id = t.id
        WHERE 1=1
    """
    params = []
    if q:
        sql += " AND (t.titulo LIKE ? OR t.autor LIKE ? OR t.isbn LIKE ?)"
        params += [f'%{q}%', f'%{q}%', f'%{q}%']
    if cat:
        sql += " AND t.categoria = ?"
        params.append(cat)
    sql += " GROUP BY t.id ORDER BY t.titulo"
    titulos = con.execute(sql, params).fetchall()
    categorias = [r[0] for r in con.execute("SELECT DISTINCT categoria FROM titulos WHERE categoria IS NOT NULL ORDER BY categoria").fetchall()]
    con.close()
    return render_template('libros.html', titulos=titulos, categorias=categorias, q=q, cat=cat)

@app.route('/libros/nuevo', methods=['GET','POST'])
@login_required
def libro_nuevo():
    if request.method == 'POST':
        con = get_db()
        cur = con.execute("""
            INSERT INTO titulos (titulo,autor,categoria,isbn,anio)
            VALUES (?,?,?,?,?)
        """, (request.form['titulo'], request.form['autor'],
              request.form.get('categoria'), request.form.get('isbn'),
              request.form.get('anio') or None))
        titulo_id = cur.lastrowid
        cantidad = int(request.form.get('cantidad', 1))
        for i in range(1, cantidad + 1):
            con.execute("INSERT INTO ejemplares (titulo_id, numero) VALUES (?,?)", (titulo_id, i))
        con.commit()
        con.close()
        flash(f'Libro agregado con {cantidad} ejemplar(es)')
        return redirect(url_for('libros'))
    return render_template('libro_form.html', titulo=None)

@app.route('/libros/<int:tid>')
@login_required
def libro_detalle(tid):
    con = get_db()
    titulo = con.execute("SELECT * FROM titulos WHERE id=?", (tid,)).fetchone()
    ejemplares = con.execute("""
        SELECT e.*, p.alumno, p.grado, p.fin
        FROM ejemplares e
        LEFT JOIN prestamos p ON p.ejemplar_id = e.id AND p.devuelto IS NULL
        WHERE e.titulo_id = ?
        ORDER BY e.numero
    """, (tid,)).fetchall()
    historial = con.execute("""
        SELECT p.*, e.numero
        FROM prestamos p
        JOIN ejemplares e ON e.id = p.ejemplar_id
        WHERE e.titulo_id = ? AND p.devuelto IS NOT NULL
        ORDER BY p.devuelto DESC LIMIT 20
    """, (tid,)).fetchall()
    con.close()
    return render_template('libro_detalle.html', titulo=titulo, ejemplares=ejemplares, historial=historial)

@app.route('/libros/<int:tid>/agregar_ejemplares', methods=['POST'])
@login_required
def agregar_ejemplares(tid):
    cantidad = int(request.form.get('cantidad', 1))
    con = get_db()
    ultimo = con.execute("SELECT MAX(numero) FROM ejemplares WHERE titulo_id=?", (tid,)).fetchone()[0] or 0
    for i in range(1, cantidad + 1):
        con.execute("INSERT INTO ejemplares (titulo_id, numero) VALUES (?,?)", (tid, ultimo + i))
    con.commit()
    con.close()
    flash(f'{cantidad} ejemplar(es) agregados')
    return redirect(url_for('libro_detalle', tid=tid))

@app.route('/libros/<int:tid>/eliminar', methods=['POST'])
@admin_required
def libro_eliminar(tid):
    con = get_db()
    prestados = con.execute("""
        SELECT COUNT(*) FROM ejemplares e
        JOIN prestamos p ON p.ejemplar_id = e.id
        WHERE e.titulo_id = ? AND p.devuelto IS NULL
    """, (tid,)).fetchone()[0]
    if prestados > 0:
        flash('No se puede eliminar: hay ejemplares prestados actualmente')
    else:
        con.execute("DELETE FROM titulos WHERE id=?", (tid,))
        con.commit()
        flash('Libro eliminado')
    con.close()
    return redirect(url_for('libros'))

# ── préstamos ─────────────────────────────────────────────────────────────────

@app.route('/prestamos')
@login_required
def prestamos():
    hoy = date.today().isoformat()
    q = request.args.get('q','')
    estado = request.args.get('estado','')
    con = get_db()
    sql = """
        SELECT p.*, e.numero, t.titulo, t.autor,
               CASE
                 WHEN p.devuelto IS NOT NULL THEN 'devuelto'
                 WHEN p.fin < ? THEN 'vencido'
                 WHEN p.fin = ? THEN 'vence_hoy'
                 ELSE 'activo'
               END AS estado_calc
        FROM prestamos p
        JOIN ejemplares e ON e.id = p.ejemplar_id
        JOIN titulos t ON t.id = e.titulo_id
        WHERE 1=1
    """
    params = [hoy, hoy]
    if q:
        sql += " AND (p.alumno LIKE ? OR t.titulo LIKE ? OR p.grado LIKE ?)"
        params += [f'%{q}%', f'%{q}%', f'%{q}%']
    if estado == 'activo':
        sql += " AND p.devuelto IS NULL AND p.fin >= ?"
        params.append(hoy)
    elif estado == 'vencido':
        sql += " AND p.devuelto IS NULL AND p.fin < ?"
        params.append(hoy)
    elif estado == 'devuelto':
        sql += " AND p.devuelto IS NOT NULL"
    sql += " ORDER BY p.id DESC"
    lista = con.execute(sql, params).fetchall()
    con.close()
    return render_template('prestamos.html', lista=lista, q=q, estado=estado, hoy=hoy)

@app.route('/prestamos/nuevo', methods=['GET','POST'])
@login_required
def prestamo_nuevo():
    if request.method == 'POST':
        ejemplar_id = request.form['ejemplar_id']
        alumno = request.form['alumno'].strip()
        grado = request.form.get('grado','').strip()
        semanas = int(request.form.get('semanas', 1))
        nota = request.form.get('nota','').strip()
        if semanas > 3:
            semanas = 3
        fin = (date.today() + timedelta(weeks=semanas)).isoformat()
        con = get_db()
        ej = con.execute("SELECT estado FROM ejemplares WHERE id=?", (ejemplar_id,)).fetchone()
        if not ej or ej['estado'] != 'disponible':
            flash('Este ejemplar ya está prestado')
            return redirect(url_for('prestamo_nuevo'))
        con.execute("""
            INSERT INTO prestamos (ejemplar_id, alumno, grado, inicio, fin, creado_por, nota)
            VALUES (?,?,?,?,?,?,?)
        """, (ejemplar_id, alumno, grado, date.today().isoformat(), fin,
              session['user']['usuario'], nota))
        con.execute("UPDATE ejemplares SET estado='prestado' WHERE id=?", (ejemplar_id,))
        con.commit()
        con.close()
        flash(f'Préstamo registrado para {alumno} — devolución: {fin}')
        return redirect(url_for('prestamos'))
    con = get_db()
    titulos = con.execute("""
        SELECT t.id, t.titulo, t.autor,
               COUNT(e.id) AS disponibles
        FROM titulos t
        JOIN ejemplares e ON e.titulo_id = t.id AND e.estado='disponible'
        GROUP BY t.id
        HAVING disponibles > 0
        ORDER BY t.titulo
    """).fetchall()
    con.close()
    return render_template('prestamo_form.html', titulos=titulos)

@app.route('/prestamos/ejemplares/<int:titulo_id>')
@login_required
def ejemplares_disponibles(titulo_id):
    con = get_db()
    rows = con.execute("""
        SELECT id, numero FROM ejemplares
        WHERE titulo_id=? AND estado='disponible'
        ORDER BY numero
    """, (titulo_id,)).fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])

@app.route('/prestamos/<int:pid>/devolver', methods=['POST'])
@login_required
def devolver(pid):
    con = get_db()
    p = con.execute("SELECT * FROM prestamos WHERE id=?", (pid,)).fetchone()
    if p and not p['devuelto']:
        con.execute("UPDATE prestamos SET devuelto=? WHERE id=?", (date.today().isoformat(), pid))
        con.execute("UPDATE ejemplares SET estado='disponible' WHERE id=?", (p['ejemplar_id'],))
        con.commit()
        flash('Devolución registrada')
    con.close()
    return redirect(request.referrer or url_for('prestamos'))

# ── donaciones ────────────────────────────────────────────────────────────────

@app.route('/donaciones')
@login_required
def donaciones():
    con = get_db()
    lista = con.execute("""
        SELECT d.*, t.titulo, t.autor
        FROM donaciones d
        LEFT JOIN titulos t ON t.id = d.titulo_id
        ORDER BY d.id DESC
    """).fetchall()
    con.close()
    return render_template('donaciones.html', lista=lista)

@app.route('/donaciones/nueva', methods=['GET','POST'])
@login_required
def donacion_nueva():
    if request.method == 'POST':
        donante = request.form['donante'].strip()
        cantidad = int(request.form.get('cantidad', 1))
        fecha = request.form.get('fecha') or date.today().isoformat()
        nota = request.form.get('nota','').strip()
        modo = request.form.get('modo')
        con = get_db()
        if modo == 'existente':
            titulo_id = int(request.form['titulo_id'])
            ultimo = con.execute("SELECT MAX(numero) FROM ejemplares WHERE titulo_id=?", (titulo_id,)).fetchone()[0] or 0
            for i in range(1, cantidad + 1):
                con.execute("INSERT INTO ejemplares (titulo_id, numero, nota) VALUES (?,?,?)",
                            (titulo_id, ultimo + i, 'Donado por ' + donante))
        else:
            cur = con.execute("""
                INSERT INTO titulos (titulo,autor,categoria,isbn)
                VALUES (?,?,?,?)
            """, (request.form['titulo'], request.form['autor'],
                  request.form.get('categoria',''), request.form.get('isbn','')))
            titulo_id = cur.lastrowid
            for i in range(1, cantidad + 1):
                con.execute("INSERT INTO ejemplares (titulo_id, numero, nota) VALUES (?,?,?)",
                            (titulo_id, i, 'Donado por ' + donante))
        con.execute("INSERT INTO donaciones (donante,titulo_id,cantidad,fecha,nota) VALUES (?,?,?,?,?)",
                    (donante, titulo_id, cantidad, fecha, nota))
        con.commit()
        con.close()
        flash(f'Donación de {cantidad} ejemplar(es) registrada y añadida al inventario')
        return redirect(url_for('donaciones'))
    con = get_db()
    titulos = con.execute("SELECT id, titulo, autor FROM titulos ORDER BY titulo").fetchall()
    con.close()
    return render_template('donacion_form.html', titulos=titulos)

# ── reportes ──────────────────────────────────────────────────────────────────

@app.route('/reportes')
@admin_required
def reportes():
    hoy = date.today().isoformat()
    con = get_db()
    mas_prestados = con.execute("""
        SELECT t.titulo, t.autor, COUNT(p.id) AS veces
        FROM prestamos p
        JOIN ejemplares e ON e.id = p.ejemplar_id
        JOIN titulos t ON t.id = e.titulo_id
        GROUP BY t.id ORDER BY veces DESC LIMIT 10
    """).fetchall()
    por_categoria = con.execute("""
        SELECT t.categoria, COUNT(e.id) AS total,
               SUM(CASE WHEN e.estado='prestado' THEN 1 ELSE 0 END) AS prestados
        FROM titulos t
        JOIN ejemplares e ON e.titulo_id = t.id
        WHERE t.categoria IS NOT NULL
        GROUP BY t.categoria ORDER BY total DESC
    """).fetchall()
    alumnos_vencidos = con.execute("""
        SELECT p.alumno, p.grado, t.titulo, e.numero, p.fin,
               CAST(julianday('now') - julianday(p.fin) AS INTEGER) AS dias
        FROM prestamos p
        JOIN ejemplares e ON e.id = p.ejemplar_id
        JOIN titulos t ON t.id = e.titulo_id
        WHERE p.devuelto IS NULL AND p.fin < ?
        ORDER BY p.fin ASC
    """, (hoy,)).fetchall()
    con.close()
    return render_template('reportes.html', mas_prestados=mas_prestados,
                           por_categoria=por_categoria, alumnos_vencidos=alumnos_vencidos)

# ── usuarios (solo admin) ─────────────────────────────────────────────────────

@app.route('/usuarios')
@admin_required
def usuarios():
    con = get_db()
    lista = con.execute("SELECT id, nombre, usuario, rol FROM usuarios ORDER BY rol, nombre").fetchall()
    con.close()
    return render_template('usuarios.html', lista=lista)

@app.route('/usuarios/nuevo', methods=['GET','POST'])
@admin_required
def usuario_nuevo():
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        usuario = request.form['usuario'].strip()
        password = request.form['password'].strip()
        rol = request.form.get('rol', 'encargado')
        if not nombre or not usuario or not password:
            flash('Todos los campos son obligatorios')
            return redirect(url_for('usuario_nuevo'))
        con = get_db()
        try:
            con.execute("INSERT INTO usuarios (nombre,usuario,password,rol) VALUES (?,?,?,?)",
                        (nombre, usuario, hash_pw(password), rol))
            con.commit()
            flash(f'Usuario "{usuario}" creado correctamente')
            return redirect(url_for('usuarios'))
        except sqlite3.IntegrityError:
            flash(f'El usuario "{usuario}" ya existe')
        finally:
            con.close()
    return render_template('usuario_form.html', u=None)

@app.route('/usuarios/<int:uid>/editar', methods=['GET','POST'])
@admin_required
def usuario_editar(uid):
    con = get_db()
    u = con.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    con.close()
    if not u:
        flash('Usuario no encontrado')
        return redirect(url_for('usuarios'))
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        usuario = request.form['usuario'].strip()
        rol = request.form.get('rol', 'encargado')
        password = request.form['password'].strip()
        con = get_db()
        try:
            if password:
                con.execute("UPDATE usuarios SET nombre=?,usuario=?,rol=?,password=? WHERE id=?",
                            (nombre, usuario, rol, hash_pw(password), uid))
            else:
                con.execute("UPDATE usuarios SET nombre=?,usuario=?,rol=? WHERE id=?",
                            (nombre, usuario, rol, uid))
            con.commit()
            flash('Usuario actualizado')
            # actualizar sesión si es el mismo usuario
            if session['user']['id'] == uid:
                session['user']['nombre'] = nombre
                session['user']['usuario'] = usuario
                session['user']['rol'] = rol
            return redirect(url_for('usuarios'))
        except sqlite3.IntegrityError:
            flash(f'El usuario "{usuario}" ya existe')
        finally:
            con.close()
    return render_template('usuario_form.html', u=u)

@app.route('/usuarios/<int:uid>/eliminar', methods=['POST'])
@admin_required
def usuario_eliminar(uid):
    if session['user']['id'] == uid:
        flash('No puedes eliminar tu propio usuario')
        return redirect(url_for('usuarios'))
    con = get_db()
    con.execute("DELETE FROM usuarios WHERE id=?", (uid,))
    con.commit()
    con.close()
    flash('Usuario eliminado')
    return redirect(url_for('usuarios'))

# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    print("\n  Biblioteca escolar iniciada")
    print("  Abre tu navegador en: biblioteca-cejaeg-production-c612.up.railway.app")
    print("  Usuario: admin  |  Contraseña: admin123\n")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))