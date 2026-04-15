-- 数据库: yonbip_fi_ctmfm
-- 表: tlm_voucher 凭证表

CREATE TABLE `tlm_voucher` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `ytenant_id` varchar(36) DEFAULT NULL COMMENT '租户ID',
  `voucher_no` varchar(64) NOT NULL COMMENT '凭证号',
  `voucher_date` date NOT NULL COMMENT '凭证日期',
  `accounting_period` varchar(10) DEFAULT NULL COMMENT '会计期间',
  `debit_amount` decimal(18,2) DEFAULT '0.00' COMMENT '借方金额',
  `credit_amount` decimal(18,2) DEFAULT '0.00' COMMENT '贷方金额',
  `currency_code` varchar(10) DEFAULT 'CNY' COMMENT '币种代码',
  `exchange_rate` decimal(18,8) DEFAULT '1.00000000' COMMENT '汇率',
  `original_currency_amount` decimal(18,2) DEFAULT '0.00' COMMENT '原币金额',
  `summary` varchar(500) DEFAULT NULL COMMENT '摘要',
  `attachment_count` int(11) DEFAULT '0' COMMENT '附件数量',
  `status` varchar(20) DEFAULT 'draft' COMMENT '状态:draft-草稿,posted-已过账,cancelled-已作废',
  `creator` varchar(64) DEFAULT NULL COMMENT '制单人',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `modifier` varchar(64) DEFAULT NULL COMMENT '修改人',
  `modify_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `is_deleted` tinyint(1) DEFAULT '0' COMMENT '是否删除:0-否,1-是',
  PRIMARY KEY (`id`),
  KEY `idx_voucher_no` (`voucher_no`),
  KEY `idx_voucher_date` (`voucher_date`),
  KEY `idx_ytenant_id` (`ytenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='凭证主表';

-- 表: tlm_voucher_entry 凭证明细表

CREATE TABLE `tlm_voucher_entry` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `ytenant_id` varchar(36) DEFAULT NULL COMMENT '租户ID',
  `voucher_id` bigint(20) NOT NULL COMMENT '凭证ID',
  `entry_no` int(11) NOT NULL COMMENT '分录序号',
  `account_code` varchar(64) NOT NULL COMMENT '科目代码',
  `account_name` varchar(128) DEFAULT NULL COMMENT '科目名称',
  `debit_amount` decimal(18,2) DEFAULT '0.00' COMMENT '借方金额',
  `credit_amount` decimal(18,2) DEFAULT '0.00' COMMENT '贷方金额',
  `summary` varchar(500) DEFAULT NULL COMMENT '摘要',
  `auxiliary_code` varchar(64) DEFAULT NULL COMMENT '辅助核算代码',
  `auxiliary_name` varchar(128) DEFAULT NULL COMMENT '辅助核算名称',
  `project_code` varchar(64) DEFAULT NULL COMMENT '项目代码',
  `department_code` varchar(64) DEFAULT NULL COMMENT '部门代码',
  `person_code` varchar(64) DEFAULT NULL COMMENT '人员代码',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `is_deleted` tinyint(1) DEFAULT '0' COMMENT '是否删除',
  PRIMARY KEY (`id`),
  KEY `idx_voucher_id` (`voucher_id`),
  KEY `idx_account_code` (`account_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='凭证明细表';

-- 表: tlm_contract 合同表

CREATE TABLE `tlm_contract` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `ytenant_id` varchar(36) DEFAULT NULL COMMENT '租户ID',
  `contract_no` varchar(64) NOT NULL COMMENT '合同编号',
  `contract_name` varchar(256) NOT NULL COMMENT '合同名称',
  `contract_type` varchar(32) DEFAULT NULL COMMENT '合同类型',
  `counterparty_name` varchar(256) DEFAULT NULL COMMENT '对方单位名称',
  `counterparty_code` varchar(64) DEFAULT NULL COMMENT '对方单位代码',
  `contract_amount` decimal(18,2) DEFAULT '0.00' COMMENT '合同金额',
  `sign_date` date DEFAULT NULL COMMENT '签订日期',
  `start_date` date DEFAULT NULL COMMENT '开始日期',
  `end_date` date DEFAULT NULL COMMENT '结束日期',
  `payment_terms` varchar(500) DEFAULT NULL COMMENT '付款条款',
  `responsible_person` varchar(64) DEFAULT NULL COMMENT '负责人',
  `department_code` varchar(64) DEFAULT NULL COMMENT '部门代码',
  `status` varchar(20) DEFAULT 'active' COMMENT '状态',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `is_deleted` tinyint(1) DEFAULT '0' COMMENT '是否删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_contract_no` (`contract_no`),
  KEY `idx_counterparty` (`counterparty_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='合同主表';

