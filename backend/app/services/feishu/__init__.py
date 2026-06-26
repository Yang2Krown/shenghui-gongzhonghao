"""飞书商单 brief 接入服务。

P1：通过 lark-cli 落地设备码 OAuth + 读文档，按 user_id 隔离配置目录实现多用户。
后续可把 client 换成原生飞书 HTTP OAuth，而不动 reader / summarizer / API。
"""
