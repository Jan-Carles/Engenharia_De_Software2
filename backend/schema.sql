-- Tabelas do projeto (as mesmas do arquivo tabelas_ddl)
CREATE TABLE IF NOT EXISTS peca_roupa (
    id_peca SERIAL PRIMARY KEY,
    modelo VARCHAR(100) NOT NULL,
    categoria VARCHAR(50) NOT NULL,
    genero VARCHAR(20) NOT NULL,
    corte VARCHAR(30) NOT NULL
);

CREATE TABLE IF NOT EXISTS tamanho (
    id_tamanho SERIAL PRIMARY KEY,
    id_peca INT NOT NULL,
    tamanho VARCHAR(10) NOT NULL,
    FOREIGN KEY (id_peca) REFERENCES peca_roupa(id_peca),
    UNIQUE (id_peca, tamanho)
);

CREATE TABLE IF NOT EXISTS medida (
    id_medida SERIAL PRIMARY KEY,
    id_tamanho INT NOT NULL,
    ombro DECIMAL(6,2) NOT NULL,
    cintura DECIMAL(6,2) NOT NULL,
    altura DECIMAL(6,2) NOT NULL,
    busto DECIMAL(6,2) NOT NULL,
    FOREIGN KEY (id_tamanho) REFERENCES tamanho(id_tamanho),
    UNIQUE (id_tamanho)
);

-- OPCIONAL (recomendado): garante a regra de peça duplicada no próprio banco,
-- mesmo se duas requisições chegarem ao mesmo tempo.
CREATE UNIQUE INDEX IF NOT EXISTS uq_peca_duplicada
    ON peca_roupa (lower(modelo), categoria, genero, corte);
