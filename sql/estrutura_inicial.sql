-- Estrutura vazia para MySQL 8.0+. Selecione um banco vazio antes de executar.
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `historico_alteracoes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `usuario_id` int DEFAULT NULL,
  `usuario_nome` varchar(100) DEFAULT NULL,
  `tabela` varchar(50) DEFAULT NULL,
  `registro_id` int DEFAULT NULL,
  `acao` varchar(50) DEFAULT NULL,
  `detalhes` text,
  `data_alteracao` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `produtos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `sku` varchar(50) NOT NULL,
  `descricao` varchar(255) NOT NULL COMMENT 'Descrição/nome do produto',
  `marca` varchar(100) DEFAULT NULL COMMENT 'Marca (usado no filtro do app)',
  `trib` decimal(10,2) DEFAULT NULL COMMENT 'Custo + tributo já calculado',
  `embalagem` varchar(50) DEFAULT NULL COMMENT 'Tipo de embalagem',
  `quantidade` int DEFAULT '0' COMMENT 'Estoque disponível',
  `target_minimo` decimal(10,2) DEFAULT NULL COMMENT 'Preço mínimo alvo',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `peso` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_sku` (`sku`),
  KEY `idx_marca` (`marca`),
  KEY `idx_descricao` (`descricao`),
  KEY `idx_produtos_sku` (`sku`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `produtos_amazon` (
  `id` int NOT NULL AUTO_INCREMENT,
  `produto_id` int NOT NULL,
  `preco_real` decimal(10,2) DEFAULT NULL,
  `sugestao_preco` varchar(50) DEFAULT NULL,
  `frete` decimal(10,2) DEFAULT NULL,
  `lucro` decimal(10,2) DEFAULT NULL,
  `margem_lucro` decimal(10,2) DEFAULT NULL,
  `vinte_por_cento` decimal(10,2) DEFAULT NULL,
  `criado_em` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_produto_amazon` (`produto_id`),
  UNIQUE KEY `uk_amazon_produto` (`produto_id`),
  KEY `idx_amazon_produto_id` (`produto_id`),
  CONSTRAINT `produtos_amazon_ibfk_1` FOREIGN KEY (`produto_id`) REFERENCES `produtos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `produtos_kwai` (
  `id` int NOT NULL AUTO_INCREMENT,
  `produto_id` int NOT NULL,
  `preco_real` decimal(10,2) DEFAULT NULL,
  `sugestao_preco` varchar(50) DEFAULT NULL,
  `frete` decimal(10,2) DEFAULT NULL,
  `lucro` decimal(10,2) DEFAULT NULL,
  `margem_lucro` decimal(10,2) DEFAULT NULL,
  `vinte_por_cento` decimal(10,2) DEFAULT NULL,
  `criado_em` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_produto_kwai` (`produto_id`),
  UNIQUE KEY `uk_kwai_produto` (`produto_id`),
  KEY `idx_kwai_produto_id` (`produto_id`),
  CONSTRAINT `produtos_kwai_ibfk_1` FOREIGN KEY (`produto_id`) REFERENCES `produtos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `produtos_magalu` (
  `id` int NOT NULL AUTO_INCREMENT,
  `produto_id` int NOT NULL,
  `preco_real` decimal(10,2) DEFAULT NULL,
  `sugestao_preco` varchar(50) DEFAULT NULL,
  `frete` decimal(10,2) DEFAULT NULL,
  `lucro` decimal(10,2) DEFAULT NULL,
  `margem_lucro` decimal(10,2) DEFAULT NULL,
  `vinte_por_cento` decimal(10,2) DEFAULT NULL,
  `criado_em` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_produto_magalu` (`produto_id`),
  UNIQUE KEY `uk_magalu_produto` (`produto_id`),
  KEY `idx_magalu_produto_id` (`produto_id`),
  CONSTRAINT `produtos_magalu_ibfk_1` FOREIGN KEY (`produto_id`) REFERENCES `produtos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `produtos_ml` (
  `id` int NOT NULL AUTO_INCREMENT,
  `produto_id` int NOT NULL,
  `preco_real` decimal(10,2) DEFAULT NULL,
  `sugestao_preco` varchar(50) DEFAULT NULL,
  `frete` decimal(10,2) DEFAULT NULL,
  `condicao` varchar(20) DEFAULT 'Premium',
  `lucro` decimal(10,2) DEFAULT NULL,
  `margem_lucro` decimal(10,2) DEFAULT NULL,
  `vinte_por_cento` decimal(10,2) DEFAULT NULL,
  `criado_em` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_produto_ml` (`produto_id`),
  UNIQUE KEY `uk_ml_produto` (`produto_id`),
  KEY `idx_ml_produto_id` (`produto_id`),
  CONSTRAINT `produtos_ml_ibfk_1` FOREIGN KEY (`produto_id`) REFERENCES `produtos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `produtos_shopee` (
  `id` int NOT NULL AUTO_INCREMENT,
  `produto_id` int NOT NULL,
  `preco_real` decimal(10,2) DEFAULT NULL,
  `sugestao_preco` varchar(50) DEFAULT NULL,
  `frete` decimal(10,2) DEFAULT NULL,
  `lucro` decimal(10,2) DEFAULT NULL,
  `margem_lucro` decimal(10,2) DEFAULT NULL,
  `vinte_por_cento` decimal(10,2) DEFAULT NULL,
  `criado_em` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_produto_shopee` (`produto_id`),
  UNIQUE KEY `uk_shopee_produto` (`produto_id`),
  KEY `idx_shopee_produto_id` (`produto_id`),
  CONSTRAINT `produtos_shopee_ibfk_1` FOREIGN KEY (`produto_id`) REFERENCES `produtos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `produtos_tiktok` (
  `id` int NOT NULL AUTO_INCREMENT,
  `produto_id` int NOT NULL,
  `preco_real` decimal(10,2) DEFAULT NULL,
  `sugestao_preco` varchar(50) DEFAULT NULL,
  `frete` decimal(10,2) DEFAULT NULL,
  `lucro` decimal(10,2) DEFAULT NULL,
  `margem_lucro` decimal(10,2) DEFAULT NULL,
  `vinte_por_cento` decimal(10,2) DEFAULT NULL,
  `criado_em` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_produto_tiktok` (`produto_id`),
  UNIQUE KEY `uk_tiktok_produto` (`produto_id`),
  KEY `idx_tiktok_produto_id` (`produto_id`),
  CONSTRAINT `produtos_tiktok_ibfk_1` FOREIGN KEY (`produto_id`) REFERENCES `produtos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `tabela_frete_amazon` (
  `id` int NOT NULL AUTO_INCREMENT,
  `peso` varchar(30) NOT NULL,
  `faixa_79_99_99` decimal(10,2) NOT NULL,
  `faixa_100_119_99` decimal(10,2) NOT NULL,
  `faixa_120_149_99` decimal(10,2) NOT NULL,
  `faixa_150_199_99` decimal(10,2) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `tabela_frete_amazon_brl200` (
  `id` int NOT NULL AUTO_INCREMENT,
  `peso` varchar(30) NOT NULL,
  `sp_capital` decimal(10,2) NOT NULL,
  `outras_capitais_sul_sudeste` decimal(10,2) NOT NULL,
  `interior_sul_sudeste` decimal(10,2) NOT NULL,
  `centro_oeste_norte_nordeste` decimal(10,2) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `tabela_frete_ml` (
  `id` int NOT NULL AUTO_INCREMENT,
  `peso` varchar(50) NOT NULL,
  `faixa_0_18_99` decimal(10,2) NOT NULL,
  `faixa_19_48_99` decimal(10,2) NOT NULL,
  `faixa_49_78_99` decimal(10,2) NOT NULL,
  `faixa_79_99_99` decimal(10,2) NOT NULL,
  `faixa_100_119_99` decimal(10,2) NOT NULL,
  `faixa_120_149_99` decimal(10,2) NOT NULL,
  `faixa_150_199_99` decimal(10,2) NOT NULL,
  `faixa_200_mais` decimal(10,2) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `tabela_frete_shopee` (
  `id` int NOT NULL AUTO_INCREMENT,
  `faixa` varchar(20) NOT NULL,
  `valor_do_produto` varchar(50) NOT NULL,
  `taxa_percentual` decimal(5,2) NOT NULL,
  `taxa_fixa_reais` decimal(10,2) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `tabela_taxas_comissoes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `canal` varchar(30) NOT NULL,
  `condicao` varchar(50) NOT NULL,
  `taxa_percentual` decimal(5,2) NOT NULL,
  `taxa_fixa_reais` decimal(10,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_taxas_canal_condicao` (`canal`,`condicao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `usuarios` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nome` varchar(100) NOT NULL,
  `email` varchar(150) NOT NULL,
  `senha_hash` varchar(255) NOT NULL,
  `role` enum('admin','usuario') DEFAULT 'usuario',
  `ativo` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`),
  KEY `idx_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
