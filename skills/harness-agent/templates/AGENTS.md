---
type: Agent Instructions
title: Harness 文档准则
description: 规定写入权限、文档归属、格式和内容。
status: stable
---

# Harness 文档准则

开始工作前，必须读取 [index.md](index.md)。
按任务读取索引指向的文档，并遵循适用的规范与设计。

## 写入准则

写入须有人类明确要求或事先同意，普通开发任务不自动授权。
授权包含必需的引用与索引同步，工具写入同样受限。

## 文档归属

`harness/` 维护准则、架构、设计和合同。
实现说明、构建命令和测试结果保留原位置，根 `AGENTS.md` 只保留入口和操作说明。

## 文档格式

文档采用 Open Knowledge Format（OKF）v0.2，概念文档须有 `type`、`title` 和 `status` 元数据。
根索引声明 `okf_version: "0.2"`，子索引不含元数据，内部文档使用相对链接。

## 文档内容

正文只描述确定的终态规范与设计，不保留中间方案、讨论过程或实现进度。
变更直接更新正文，历史由 Git 保存，终态设计不代表实现已完成。
