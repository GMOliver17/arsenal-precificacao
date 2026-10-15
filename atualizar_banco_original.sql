-- Atualizacao do banco ORIGINAL para a versao atual do Arsenal.
-- MySQL 8.0+. Selecione o banco correto antes de executar TODO o arquivo.
-- Feche o aplicativo e faca um backup completo antes de iniciar.
-- Nao apaga produtos, nao substitui regras e nao recalcula precos.
-- Pode ser executado novamente. DDL no MySQL possui commit implicito.
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS precificacao_controle (
        id INT PRIMARY KEY, versao INT NOT NULL DEFAULT 0) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS precificacao_resultados (
        produto_id INT NOT NULL, plataforma VARCHAR(30) NOT NULL,
        status VARCHAR(20) NOT NULL, mensagem TEXT, dados JSON NOT NULL,
        atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (produto_id, plataforma),
        FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS empresas (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, nome VARCHAR(160) NOT NULL,
            cnpj VARCHAR(14) NOT NULL UNIQUE,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS migracoes_sistema (
            chave VARCHAR(80) PRIMARY KEY, versao INT NOT NULL,
            aplicado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO precificacao_controle (id,versao) VALUES (1,0);

-- Interrompa se a empresa 1 ja existir com outro cadastro.
-- A chave unica impede duplicar o CNPJ.
INSERT INTO empresas (id,nome,cnpj)
SELECT 1,'Empresa inicial','00000000000000'
WHERE NOT EXISTS (SELECT 1 FROM empresas WHERE id=1);


-- produtos

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='produtos' AND COLUMN_NAME='empresa_id'), 'ALTER TABLE `produtos` ADD COLUMN empresa_id INT NULL', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

-- Preserve timestamps com ON UPDATE durante o vinculo dos dados existentes.
SELECT GROUP_CONCAT(CONCAT(', `',COLUMN_NAME,'`=`',COLUMN_NAME,'`') SEPARATOR '')
INTO @arsenal_datas FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='produtos' AND LOWER(EXTRA) LIKE '%on update%';
SET @arsenal_sql=CONCAT('UPDATE `produtos` SET empresa_id=1',COALESCE(@arsenal_datas,''),' WHERE empresa_id IS NULL');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='produtos' AND COLUMN_NAME='empresa_id' AND IS_NULLABLE='YES'), 'ALTER TABLE `produtos` MODIFY COLUMN empresa_id INT NOT NULL', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='produtos' AND INDEX_NAME='idx_empresa_sku'), 'CREATE INDEX `idx_empresa_sku` ON `produtos` (empresa_id,sku)', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME='produtos' AND CONSTRAINT_NAME='fk_produtos_empresa'), 'ALTER TABLE `produtos` ADD CONSTRAINT `fk_produtos_empresa` FOREIGN KEY (empresa_id) REFERENCES empresas(id)', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;


-- tabela_taxas_comissoes

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_taxas_comissoes' AND COLUMN_NAME='empresa_id'), 'ALTER TABLE `tabela_taxas_comissoes` ADD COLUMN empresa_id INT NULL', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

-- Preserve timestamps com ON UPDATE durante o vinculo dos dados existentes.
SELECT GROUP_CONCAT(CONCAT(', `',COLUMN_NAME,'`=`',COLUMN_NAME,'`') SEPARATOR '')
INTO @arsenal_datas FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_taxas_comissoes' AND LOWER(EXTRA) LIKE '%on update%';
SET @arsenal_sql=CONCAT('UPDATE `tabela_taxas_comissoes` SET empresa_id=1',COALESCE(@arsenal_datas,''),' WHERE empresa_id IS NULL');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_taxas_comissoes' AND COLUMN_NAME='empresa_id' AND IS_NULLABLE='YES'), 'ALTER TABLE `tabela_taxas_comissoes` MODIFY COLUMN empresa_id INT NOT NULL', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_taxas_comissoes' AND INDEX_NAME='idx_empresa'), 'CREATE INDEX `idx_empresa` ON `tabela_taxas_comissoes` (empresa_id)', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME='tabela_taxas_comissoes' AND CONSTRAINT_NAME='fk_tabela_taxas_comissoes_empresa'), 'ALTER TABLE `tabela_taxas_comissoes` ADD CONSTRAINT `fk_tabela_taxas_comissoes_empresa` FOREIGN KEY (empresa_id) REFERENCES empresas(id)', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;


-- tabela_frete_ml

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_ml' AND COLUMN_NAME='empresa_id'), 'ALTER TABLE `tabela_frete_ml` ADD COLUMN empresa_id INT NULL', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

-- Preserve timestamps com ON UPDATE durante o vinculo dos dados existentes.
SELECT GROUP_CONCAT(CONCAT(', `',COLUMN_NAME,'`=`',COLUMN_NAME,'`') SEPARATOR '')
INTO @arsenal_datas FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_ml' AND LOWER(EXTRA) LIKE '%on update%';
SET @arsenal_sql=CONCAT('UPDATE `tabela_frete_ml` SET empresa_id=1',COALESCE(@arsenal_datas,''),' WHERE empresa_id IS NULL');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_ml' AND COLUMN_NAME='empresa_id' AND IS_NULLABLE='YES'), 'ALTER TABLE `tabela_frete_ml` MODIFY COLUMN empresa_id INT NOT NULL', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_ml' AND INDEX_NAME='idx_empresa'), 'CREATE INDEX `idx_empresa` ON `tabela_frete_ml` (empresa_id)', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_ml' AND CONSTRAINT_NAME='fk_tabela_frete_ml_empresa'), 'ALTER TABLE `tabela_frete_ml` ADD CONSTRAINT `fk_tabela_frete_ml_empresa` FOREIGN KEY (empresa_id) REFERENCES empresas(id)', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;


-- tabela_frete_shopee

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_shopee' AND COLUMN_NAME='empresa_id'), 'ALTER TABLE `tabela_frete_shopee` ADD COLUMN empresa_id INT NULL', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

-- Preserve timestamps com ON UPDATE durante o vinculo dos dados existentes.
SELECT GROUP_CONCAT(CONCAT(', `',COLUMN_NAME,'`=`',COLUMN_NAME,'`') SEPARATOR '')
INTO @arsenal_datas FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_shopee' AND LOWER(EXTRA) LIKE '%on update%';
SET @arsenal_sql=CONCAT('UPDATE `tabela_frete_shopee` SET empresa_id=1',COALESCE(@arsenal_datas,''),' WHERE empresa_id IS NULL');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_shopee' AND COLUMN_NAME='empresa_id' AND IS_NULLABLE='YES'), 'ALTER TABLE `tabela_frete_shopee` MODIFY COLUMN empresa_id INT NOT NULL', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_shopee' AND INDEX_NAME='idx_empresa'), 'CREATE INDEX `idx_empresa` ON `tabela_frete_shopee` (empresa_id)', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_shopee' AND CONSTRAINT_NAME='fk_tabela_frete_shopee_empresa'), 'ALTER TABLE `tabela_frete_shopee` ADD CONSTRAINT `fk_tabela_frete_shopee_empresa` FOREIGN KEY (empresa_id) REFERENCES empresas(id)', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;


-- tabela_frete_amazon

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_amazon' AND COLUMN_NAME='empresa_id'), 'ALTER TABLE `tabela_frete_amazon` ADD COLUMN empresa_id INT NULL', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

-- Preserve timestamps com ON UPDATE durante o vinculo dos dados existentes.
SELECT GROUP_CONCAT(CONCAT(', `',COLUMN_NAME,'`=`',COLUMN_NAME,'`') SEPARATOR '')
INTO @arsenal_datas FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_amazon' AND LOWER(EXTRA) LIKE '%on update%';
SET @arsenal_sql=CONCAT('UPDATE `tabela_frete_amazon` SET empresa_id=1',COALESCE(@arsenal_datas,''),' WHERE empresa_id IS NULL');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_amazon' AND COLUMN_NAME='empresa_id' AND IS_NULLABLE='YES'), 'ALTER TABLE `tabela_frete_amazon` MODIFY COLUMN empresa_id INT NOT NULL', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_amazon' AND INDEX_NAME='idx_empresa'), 'CREATE INDEX `idx_empresa` ON `tabela_frete_amazon` (empresa_id)', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_amazon' AND CONSTRAINT_NAME='fk_tabela_frete_amazon_empresa'), 'ALTER TABLE `tabela_frete_amazon` ADD CONSTRAINT `fk_tabela_frete_amazon_empresa` FOREIGN KEY (empresa_id) REFERENCES empresas(id)', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;


-- tabela_frete_amazon_brl200

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_amazon_brl200' AND COLUMN_NAME='empresa_id'), 'ALTER TABLE `tabela_frete_amazon_brl200` ADD COLUMN empresa_id INT NULL', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

-- Preserve timestamps com ON UPDATE durante o vinculo dos dados existentes.
SELECT GROUP_CONCAT(CONCAT(', `',COLUMN_NAME,'`=`',COLUMN_NAME,'`') SEPARATOR '')
INTO @arsenal_datas FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_amazon_brl200' AND LOWER(EXTRA) LIKE '%on update%';
SET @arsenal_sql=CONCAT('UPDATE `tabela_frete_amazon_brl200` SET empresa_id=1',COALESCE(@arsenal_datas,''),' WHERE empresa_id IS NULL');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_amazon_brl200' AND COLUMN_NAME='empresa_id' AND IS_NULLABLE='YES'), 'ALTER TABLE `tabela_frete_amazon_brl200` MODIFY COLUMN empresa_id INT NOT NULL', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_amazon_brl200' AND INDEX_NAME='idx_empresa'), 'CREATE INDEX `idx_empresa` ON `tabela_frete_amazon_brl200` (empresa_id)', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME='tabela_frete_amazon_brl200' AND CONSTRAINT_NAME='fk_tabela_frete_amazon_brl200_empresa'), 'ALTER TABLE `tabela_frete_amazon_brl200` ADD CONSTRAINT `fk_tabela_frete_amazon_brl200_empresa` FOREIGN KEY (empresa_id) REFERENCES empresas(id)', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;


-- historico_alteracoes

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='historico_alteracoes' AND COLUMN_NAME='empresa_id'), 'ALTER TABLE `historico_alteracoes` ADD COLUMN empresa_id INT NULL', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

-- Preserve timestamps com ON UPDATE durante o vinculo dos dados existentes.
SELECT GROUP_CONCAT(CONCAT(', `',COLUMN_NAME,'`=`',COLUMN_NAME,'`') SEPARATOR '')
INTO @arsenal_datas FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='historico_alteracoes' AND LOWER(EXTRA) LIKE '%on update%';
SET @arsenal_sql=CONCAT('UPDATE `historico_alteracoes` SET empresa_id=1',COALESCE(@arsenal_datas,''),' WHERE empresa_id IS NULL');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='historico_alteracoes' AND COLUMN_NAME='empresa_id' AND IS_NULLABLE='YES'), 'ALTER TABLE `historico_alteracoes` MODIFY COLUMN empresa_id INT NOT NULL', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='historico_alteracoes' AND INDEX_NAME='idx_empresa'), 'CREATE INDEX `idx_empresa` ON `historico_alteracoes` (empresa_id)', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;

SET @arsenal_sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME='historico_alteracoes' AND CONSTRAINT_NAME='fk_historico_alteracoes_empresa'), 'ALTER TABLE `historico_alteracoes` ADD CONSTRAINT `fk_historico_alteracoes_empresa` FOREIGN KEY (empresa_id) REFERENCES empresas(id)', 'DO 0');
PREPARE arsenal_stmt FROM @arsenal_sql;
EXECUTE arsenal_stmt;
DEALLOCATE PREPARE arsenal_stmt;


INSERT INTO migracoes_sistema (chave,versao) VALUES ('multiempresa',1)
ON DUPLICATE KEY UPDATE versao=GREATEST(versao,1);
COMMIT;
-- Confira o cadastro e os produtos apos a execucao.
SELECT id,nome,cnpj FROM empresas ORDER BY id;
SELECT empresa_id,COUNT(*) AS total_produtos FROM produtos GROUP BY empresa_id;
-- No aplicativo, use Recalcular para atualizar os resultados antigos com as
-- formulas corrigidas. Produtos sem dados obrigatorios ficarao pendentes.
