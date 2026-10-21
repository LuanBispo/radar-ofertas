"""Execução diária: busca → filtra → registra histórico → relatório → envio.

Uso:  python -m radar.main            (usa config.yaml)
      python -m radar.main --demo     (dados fictícios, sem credenciais)
      python -m radar.main --no-send  (só gera os arquivos em reports/)
"""
import argparse
import collections
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

from . import filters, report
from .db import History
from .sources import amazon, demo, mercadolivre, painel_shopee, shopee

SOURCES = {"shopee": shopee, "painel_shopee": painel_shopee, "mercadolivre": mercadolivre,
           "amazon": amazon, "demo": demo}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--no-send", action="store_true")
    args = ap.parse_args()

    load_dotenv()
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if args.demo:
        cfg["fontes"] = {"demo": True}

    active = {n: m for n, m in SOURCES.items() if cfg["fontes"].get(n)}
    for name, mod in list(active.items()):
        if not mod.available():
            print(f"[aviso] {name}: credenciais ausentes, pulando")
            del active[name]
    if not active:
        print("Nenhuma loja com chave de API configurada ainda (ex.: Shopee). Nada a fazer hoje.")
        report.save_site([], cfg, "Aguardando a liberação da API da Shopee.", status="aguardando")
        return

    limit = cfg["relatorio"]["resultados_por_busca"]
    found, errors = [], collections.Counter()
    for name, mod in active.items():
        for cat_key, cat in cfg["categorias"].items():
            for q in cat["buscas"]:
                try:
                    for p in mod.search(q, limit, cfg):
                        p.category, p.query = cat_key, q
                        found.append(p)
                except Exception as e:  # uma busca com erro não derruba o resto
                    errors[name] += 1
                    print(f"[erro] {name} '{q}': {str(e)[:200]}")
                time.sleep(0.5)  # respeita limites de requisição

    rejected = collections.Counter()
    kept = []
    for p in filters.dedupe(found):
        why = filters.reason_to_reject(p, cfg["filtros"])
        if why:
            rejected[why] += 1
        else:
            kept.append(p)

    hist = History()
    for p in kept:
        hist.record(p)
    hist.close()

    per_source = collections.Counter(p.source for p in kept)
    stats = (f"{len(found)} resultados analisados, {len(kept)} aprovados "
             f"({', '.join(f'{report.SOURCE_LABEL[s]}: {n}' for s, n in per_source.items()) or 'nenhum'}). "
             f"Novos: {sum(p.is_new for p in kept)}. "
             f"Só produtos com nota {str(float(cfg['filtros']['avaliacao_minima'])).replace('.', ',')} ou mais.")
    if errors:
        stats += f" Falhas de busca: {dict(errors)}."
    print(stats)
    print("Descartados:", dict(rejected))

    sections = report.build_sections(kept, cfg)
    path, csv_path = report.save_files(kept, sections, stats, cfg)
    print(f"Relatório salvo em {path}")

    if not args.no_send:
        if report.send_telegram(report.to_telegram_messages(sections, stats)):
            print("Enviado no Telegram")
        if report.send_email(report.to_html(sections, stats), csv_path, len(kept)):
            print("Enviado por e-mail")


if __name__ == "__main__":
    main()
