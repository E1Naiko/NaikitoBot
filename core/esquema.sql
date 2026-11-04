-- Esquema SQLite: las fechas se guardan como texto ISO con zona.

CREATE TABLE IF NOT EXISTS box_acciones (
	id INTEGER NOT NULL,
	guild_id BIGINT NOT NULL,
	user_id BIGINT NOT NULL,
	tipo VARCHAR NOT NULL,
	iniciado_en VARCHAR NOT NULL,
	finaliza_en VARCHAR NOT NULL,
	recompensa INTEGER NOT NULL,
	dinero_recompensa INTEGER DEFAULT '0' NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS box_combates (
	id INTEGER NOT NULL,
	guild_id BIGINT NOT NULL,
	canal_id BIGINT,
	modo VARCHAR NOT NULL,
	retador_id BIGINT NOT NULL,
	contrincante_id BIGINT NOT NULL,
	semilla INTEGER NOT NULL,
	"plan" TEXT NOT NULL,
	iniciado_en VARCHAR NOT NULL,
	latido_segundos INTEGER NOT NULL,
	latidos_totales INTEGER NOT NULL,
	fin_narracion_en VARCHAR NOT NULL,
	estado VARCHAR DEFAULT 'VIVO' NOT NULL,
	mensaje_id BIGINT,
	resumen TEXT,
	terminado_en VARCHAR,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS box_config_guild (
	guild_id BIGINT NOT NULL,
	canticos INTEGER,
	actualizado_en VARCHAR,
	actualizado_por BIGINT,
	PRIMARY KEY (guild_id)
);

CREATE TABLE IF NOT EXISTS box_desafios (
	id INTEGER NOT NULL,
	guild_id BIGINT NOT NULL,
	retador_id BIGINT NOT NULL,
	contrincante_id BIGINT NOT NULL,
	expira_en VARCHAR NOT NULL,
	tipo VARCHAR DEFAULT 'SPARRING' NOT NULL,
	canal_id BIGINT,
	mensaje_id BIGINT,
	PRIMARY KEY (id),
	UNIQUE (guild_id, retador_id, contrincante_id)
);

CREATE TABLE IF NOT EXISTS box_desafios_historial (
	id INTEGER NOT NULL,
	guild_id BIGINT NOT NULL,
	retador_id BIGINT NOT NULL,
	contrincante_id BIGINT NOT NULL,
	ganador_id BIGINT NOT NULL,
	creado_en VARCHAR NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS box_equipo (
	guild_id BIGINT NOT NULL,
	user_id BIGINT NOT NULL,
	vida INTEGER DEFAULT '{BOX_VIDA_INICIAL}' NOT NULL,
	vida_maxima INTEGER DEFAULT '{BOX_VIDA_INICIAL}' NOT NULL,
	dano INTEGER DEFAULT '{BOX_DANO_INICIAL}' NOT NULL,
	dano_maximo INTEGER DEFAULT '{BOX_DANO_MAXIMO}' NOT NULL,
	defensa INTEGER DEFAULT '{BOX_DEFENSA_INICIAL}' NOT NULL,
	defensa_maxima INTEGER DEFAULT '{BOX_DEFENSA_MAXIMO}' NOT NULL,
	cansancio INTEGER DEFAULT '{BOX_CANSANCIO_INICIAL}' NOT NULL,
	cansancio_maximo INTEGER DEFAULT '{BOX_CANSANCIO_INICIAL}' NOT NULL,
	puntos_habilidad INTEGER DEFAULT '0' NOT NULL,
	casco INTEGER DEFAULT '0' NOT NULL,
	guantes INTEGER DEFAULT '0' NOT NULL,
	protector_bucal INTEGER DEFAULT '0' NOT NULL,
	short INTEGER DEFAULT '0' NOT NULL,
	botas INTEGER DEFAULT '0' NOT NULL,
	PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS box_mejoras (
	guild_id BIGINT NOT NULL,
	user_id BIGINT NOT NULL,
	mejora VARCHAR NOT NULL,
	nivel INTEGER DEFAULT '0' NOT NULL,
	PRIMARY KEY (guild_id, user_id, mejora)
);

CREATE TABLE IF NOT EXISTS box_sponsors (
	id INTEGER NOT NULL,
	guild_id BIGINT NOT NULL,
	user_id BIGINT NOT NULL,
	tipo VARCHAR NOT NULL,
	obtenido_en VARCHAR NOT NULL,
	expira_en VARCHAR NOT NULL,
	ultimo_pago VARCHAR,
	ultimo_tratamiento VARCHAR,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS box_usuarios (
	guild_id BIGINT NOT NULL,
	user_id BIGINT NOT NULL,
	experiencia INTEGER DEFAULT '0' NOT NULL,
	dinero INTEGER DEFAULT '0' NOT NULL,
	probabilidad_lesion FLOAT DEFAULT '0' NOT NULL,
	lesionado_hasta VARCHAR,
	PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS lahora_registros (
	id INTEGER NOT NULL,
	guild_id BIGINT NOT NULL,
	user_id BIGINT NOT NULL,
	username VARCHAR NOT NULL,
	fecha DATE NOT NULL,
	ventana VARCHAR NOT NULL,
	momento VARCHAR NOT NULL,
	segundos INTEGER NOT NULL,
	posicion INTEGER NOT NULL,
	puntos_base INTEGER NOT NULL,
	multiplicador FLOAT NOT NULL,
	bonus_posicion INTEGER NOT NULL,
	puntos_finales FLOAT NOT NULL,
	mensaje_id BIGINT,
	PRIMARY KEY (id),
	UNIQUE (guild_id, user_id, fecha, ventana)
);

CREATE TABLE IF NOT EXISTS lahora_sincronizacion (
	canal_id BIGINT NOT NULL,
	guild_id BIGINT NOT NULL,
	ultimo_chequeo VARCHAR NOT NULL,
	PRIMARY KEY (canal_id)
);

CREATE TABLE IF NOT EXISTS registros (
	id INTEGER NOT NULL,
	guild_id BIGINT NOT NULL,
	user_id BIGINT NOT NULL,
	username VARCHAR NOT NULL,
	fecha DATE NOT NULL,
	hora VARCHAR NOT NULL,
	puntos_base INTEGER NOT NULL,
	multiplicador FLOAT NOT NULL,
	puntos_finales FLOAT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (guild_id, user_id, fecha)
);

CREATE TABLE IF NOT EXISTS ssf_desafios (
	id INTEGER NOT NULL,
	guild_id BIGINT NOT NULL,
	nombre VARCHAR NOT NULL,
	fecha_inicio DATE NOT NULL,
	fecha_fin DATE NOT NULL,
	canal_id BIGINT NOT NULL,
	activo INTEGER DEFAULT '1' NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS box_combates_asaltos (
	combate_id INTEGER NOT NULL,
	asalto INTEGER NOT NULL,
	mensaje_id BIGINT,
	publicado_en VARCHAR NOT NULL,
	PRIMARY KEY (combate_id, asalto),
	FOREIGN KEY(combate_id) REFERENCES box_combates (id)
);

CREATE TABLE IF NOT EXISTS ssf_participantes (
	desafio_id INTEGER NOT NULL,
	user_id BIGINT NOT NULL,
	username VARCHAR NOT NULL,
	fecha_registro VARCHAR NOT NULL,
	eliminado INTEGER DEFAULT '0' NOT NULL,
	fecha_eliminacion DATE,
	racha_actual INTEGER DEFAULT '0' NOT NULL,
	mejor_racha INTEGER DEFAULT '0' NOT NULL,
	PRIMARY KEY (desafio_id, user_id),
	UNIQUE (desafio_id, user_id),
	FOREIGN KEY(desafio_id) REFERENCES ssf_desafios (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ssf_registros (
	desafio_id INTEGER NOT NULL,
	user_id BIGINT NOT NULL,
	fecha DATE NOT NULL,
	hora VARCHAR NOT NULL,
	PRIMARY KEY (desafio_id, user_id, fecha),
	UNIQUE (desafio_id, user_id, fecha),
	FOREIGN KEY(desafio_id) REFERENCES ssf_desafios (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ssf_revisiones (
	desafio_id INTEGER NOT NULL,
	ultima_fecha DATE NOT NULL,
	PRIMARY KEY (desafio_id),
	FOREIGN KEY(desafio_id) REFERENCES ssf_desafios (id) ON DELETE CASCADE
);
