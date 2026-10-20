"""Monta o relatório diário e envia por Telegram / e-mail, além de salvar HTML e CSV."""
import csv
import datetime
import html
import json
import os
import shutil
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

from .models import Product

SOURCE_LABEL = {"shopee": "Shopee", "mercadolivre": "Mercado Livre",
                "amazon": "Amazon", "demo": "Demo"}


def brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_sections(products: list[Product], cfg: dict) -> list[tuple[str, list[Product]]]:
    r = cfg["relatorio"]
    sections = []

    novos = sorted((p for p in products if p.is_new), key=lambda p: -p.commission_value)
    if novos:
        sections.append(("🆕 Novidades de hoje", novos[: r["max_novidades"]]))

    quedas = sorted((p for p in products if (p.price_drop or 0) >= r["queda_minima"]),
                    key=lambda p: -p.price_drop)
    if quedas:
        sections.append(("📉 Quedas de preço", quedas[: r["max_novidades"]]))

    top = sorted(products, key=lambda p: -p.commission_value)[: r.get("top_comissoes", 30)]
    if top:
        sections.append(("💰 Maiores comissões (quanto você ganha por venda)", top))

    for cat_key, cat in cfg["categorias"].items():
        items = sorted((p for p in products if p.category == cat_key), key=lambda p: p.price)
        if items:
            sections.append((f"{cat['nome']} — mais baratos", items[: r["top_por_categoria"]]))
    return sections


def _line_text(p: Product) -> str:
    """Linha em HTML do Telegram."""
    comm = f"{p.commission_rate:.0%}" + ("*" if p.commission_is_estimate else "")
    extras = []
    if p.price_drop:
        extras.append(f"⬇️ era {brl(p.previous_price)}")
    elif p.discount and p.discount >= 0.05:
        extras.append(f"-{p.discount:.0%}")
    if p.sales:
        extras.append(f"{p.sales} vendidos")
    if p.rating:
        extras.append(f"⭐{p.rating:.1f}")
    title = html.escape(p.title[:80])
    return (f"• <a href=\"{html.escape(p.url)}\">{title}</a>\n"
            f"   <b>{brl(p.price)}</b> · {SOURCE_LABEL[p.source]} · comissão {comm} (~{brl(p.commission_value)})"
            + (f" · {' · '.join(extras)}" if extras else ""))


def to_telegram_messages(sections, stats: str) -> list[str]:
    today = datetime.date.today().strftime("%d/%m/%Y")
    blocks = [f"<b>📊 Radar de Ofertas Tech — {today}</b>\n{html.escape(stats)}"]
    for title, items in sections:
        blocks.append(f"\n<b>{html.escape(title)}</b>")
        blocks.extend(_line_text(p) for p in items)
    blocks.append("\n<i>* comissão estimada — gere o link de afiliado no painel da plataforma.</i>")

    # Telegram aceita até 4096 caracteres por mensagem
    msgs, cur = [], ""
    for b in blocks:
        if len(cur) + len(b) > 3900:
            msgs.append(cur)
            cur = ""
        cur += b + "\n"
    if cur.strip():
        msgs.append(cur)
    return msgs


def send_telegram(messages: list[str]) -> bool:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False
    for m in messages:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
            "chat_id": chat, "text": m, "parse_mode": "HTML", "disable_web_page_preview": True,
        }, timeout=30)
        r.raise_for_status()
    return True


def to_html(sections, stats: str) -> str:
    today = datetime.date.today().strftime("%d/%m/%Y")
    parts = [f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Radar Tech {today}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:960px;margin:24px auto;padding:0 16px;color:#222}}
h2{{margin-top:32px;border-bottom:2px solid #eee;padding-bottom:4px}}
.card{{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #f0f0f0;align-items:center}}
.card img{{width:72px;height:72px;object-fit:contain;border-radius:6px;background:#fafafa}}
.price{{font-weight:700;font-size:1.1em}} .muted{{color:#666;font-size:.9em}}
.tag{{display:inline-block;background:#eef;padding:1px 6px;border-radius:4px;font-size:.8em;margin-right:4px}}
a{{color:#0a58ca;text-decoration:none}}
nav{{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}}
nav a{{background:#f2f4f8;padding:5px 10px;border-radius:999px;font-size:.85em;color:#222}}</style>
<h1>📊 Radar de Ofertas Tech — {today}</h1><p class="muted">{html.escape(stats)}</p>"""]
    # menu para pular direto para cada seção
    parts.append("<nav>" + "".join(
        f'<a href="#s{i}">{html.escape(title.split(" — ")[0].split(" (")[0])} ({len(items)})</a>'
        for i, (title, items) in enumerate(sections)) + "</nav>")
    for i, (title, items) in enumerate(sections):
        parts.append(f'<h2 id="s{i}">{html.escape(title)}</h2>')
        for p in items:
            img = f'<img src="{html.escape(p.image)}" loading="lazy">' if p.image else '<img alt="">'
            comm = f"{p.commission_rate:.0%}" + (" (estimada)" if p.commission_is_estimate else "")
            drop = f' <span class="tag">⬇️ era {brl(p.previous_price)}</span>' if p.price_drop else ""
            meta = " · ".join(x for x in [
                f"{p.sales} vendidos" if p.sales else "", f"⭐ {p.rating:.1f}" if p.rating else "",
                html.escape(p.shop or "")] if x)
            parts.append(f"""<div class="card">{img}<div>
<a href="{html.escape(p.url)}" target="_blank">{html.escape(p.title)}</a><br>
<span class="price">{brl(p.price)}</span>{drop} <span class="tag">{SOURCE_LABEL[p.source]}</span>
<span class="tag">comissão {comm} ≈ {brl(p.commission_value)}</span><br><span class="muted">{meta}</span>
</div></div>""")
    return "\n".join(parts)


def save_site(products: list[Product], cfg: dict, stats: str, status: str = "ok") -> None:
    """Publica a página da equipe: copia site/index.html e grava os dados em reports/ofertas.json."""
    out = Path("reports")
    out.mkdir(exist_ok=True)
    data = {
        "status": status,  # "ok" ou "aguardando" (sem chave de API ainda)
        "atualizado": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).isoformat(timespec="minutes"),
        "resumo": stats,
        "regras": {"nota_minima": cfg["filtros"]["avaliacao_minima"],
                   "comissao_minima": cfg["filtros"]["comissao_minima"]},
        "categorias": [{"id": k, "nome": c["nome"]} for k, c in cfg["categorias"].items()],
        "produtos": [{
            "id": p.key, "loja": p.source, "titulo": p.title, "preco": p.price,
            "preco_antes": p.original_price, "preco_ontem": p.previous_price,
            "comissao": p.commission_rate, "comissao_estimada": p.commission_is_estimate,
            "ganho": p.commission_value, "vendas": p.sales, "nota": p.rating, "loja_nome": p.shop,
            "imagem": p.image, "link": p.url, "categoria": p.category, "novo": p.is_new,
        } for p in products],
    }
    (out / "ofertas.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    shutil.copyfile("site/index.html", out / "index.html")


def save_files(products: list[Product], sections, stats: str, cfg: dict) -> tuple[Path, Path]:
    out = Path("reports")
    out.mkdir(exist_ok=True)
    day = datetime.date.today().isoformat()
    html_path = out / f"{day}.html"
    html_path.write_text(to_html(sections, stats), encoding="utf-8")
    (out / "latest.html").write_text(to_html(sections, stats), encoding="utf-8")
    save_site(products, cfg, stats)
    with open(out / f"{day}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["plataforma", "categoria", "titulo", "preco", "preco_anterior", "comissao_%",
                    "comissao_estimada", "comissao_R$", "vendas", "nota", "novo", "link"])
        for p in sorted(products, key=lambda p: (p.category, p.price)):
            w.writerow([p.source, p.category, p.title, f"{p.price:.2f}".replace(".", ","),
                        f"{p.previous_price:.2f}".replace(".", ",") if p.previous_price else "",
                        f"{p.commission_rate * 100:.1f}".replace(".", ","),
                        "sim" if p.commission_is_estimate else "não",
                        f"{p.commission_value:.2f}".replace(".", ","),
                        p.sales or "", p.rating or "", "sim" if p.is_new else "", p.url])
    return html_path, out / f"{day}.csv"


def send_email(html_body: str, csv_path: Path, total: int) -> bool:
    """Um único e-mail por dia: relatório completo no corpo + planilha com TODOS os produtos anexada."""
    user, pwd, to = (os.getenv(k) for k in ("SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO"))
    if not (user and pwd and to):
        return False
    host = os.getenv("SMTP_HOST") or "smtp.gmail.com"
    port = int(os.getenv("SMTP_PORT") or 587)

    msg = MIMEMultipart()
    msg["Subject"] = f"Radar de Ofertas Tech — {datetime.date.today():%d/%m/%Y} — {total} ofertas"
    msg["From"], msg["To"] = user, to
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    att = MIMEApplication(csv_path.read_bytes(), Name=csv_path.name)
    att["Content-Disposition"] = f'attachment; filename="{csv_path.name}"'
    msg.attach(att)

    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, pwd)
        s.sendmail(user, [a.strip() for a in to.split(",")], msg.as_string())
    return True
"""Monta o relatório diário e envia por Telegram / e-mail, além de salvar HTML e CSV."""
import csv
import datetime
import html
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

from .models import Product

SOURCE_LABEL = {"shopee": "Shopee", "mercadolivre": "Mercado Livre",
                "amazon": "Amazon", "demo": "Demo"}


def brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_sections(products: list[Product], cfg: dict) -> list[tuple[str, list[Product]]]:
    r = cfg["relatorio"]
    sections = []

    novos = sorted((p for p in products if p.is_new), key=lambda p: -p.commission_value)
    if novos:
        sections.append(("🆕 Novidades de hoje", novos[: r["max_novidades"]]))

    quedas = sorted((p for p in products if (p.price_drop or 0) >= r["queda_minima"]),
                    key=lambda p: -p.price_drop)
    if quedas:
        sections.append(("📉 Quedas de preço", quedas[: r["max_novidades"]]))

    top = sorted(products, key=lambda p: -p.commission_value)[: r.get("top_comissoes", 30)]
    if top:
        sections.append(("💰 Maiores comissões (quanto você ganha por venda)", top))

    for cat_key, cat in cfg["categorias"].items():
        items = sorted((p for p in products if p.category == cat_key), key=lambda p: p.price)
        if items:
            sections.append((f"{cat['nome']} — mais baratos", items[: r["top_por_categoria"]]))
    return sections


def _line_text(p: Product) -> str:
    """Linha em HTML do Telegram."""
    comm = f"{p.commission_rate:.0%}" + ("*" if p.commission_is_estimate else "")
    extras = []
    if p.price_drop:
        extras.append(f"⬇️ era {brl(p.previous_price)}")
    elif p.discount and p.discount >= 0.05:
        extras.append(f"-{p.discount:.0%}")
    if p.sales:
        extras.append(f"{p.sales} vendidos")
    if p.rating:
        extras.append(f"⭐{p.rating:.1f}")
    title = html.escape(p.title[:80])
    return (f"• <a href=\"{html.escape(p.url)}\">{title}</a>\n"
            f"   <b>{brl(p.price)}</b> · {SOURCE_LABEL[p.source]} · comissão {comm} (~{brl(p.commission_value)})"
            + (f" · {' · '.join(extras)}" if extras else ""))


def to_telegram_messages(sections, stats: str) -> list[str]:
    today = datetime.date.today().strftime("%d/%m/%Y")
    blocks = [f"<b>📊 Radar de Ofertas Tech — {today}</b>\n{html.escape(stats)}"]
    for title, items in sections:
        blocks.append(f"\n<b>{html.escape(title)}</b>")
        blocks.extend(_line_text(p) for p in items)
    blocks.append("\n<i>* comissão estimada — gere o link de afiliado no painel da plataforma.</i>")

    # Telegram aceita até 4096 caracteres por mensagem
    msgs, cur = [], ""
    for b in blocks:
        if len(cur) + len(b) > 3900:
            msgs.append(cur)
            cur = ""
        cur += b + "\n"
    if cur.strip():
        msgs.append(cur)
    return msgs


def send_telegram(messages: list[str]) -> bool:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False
    for m in messages:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
            "chat_id": chat, "text": m, "parse_mode": "HTML", "disable_web_page_preview": True,
        }, timeout=30)
        r.raise_for_status()
    return True


def to_html(sections, stats: str) -> str:
    today = datetime.date.today().strftime("%d/%m/%Y")
    parts = [f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Radar Tech {today}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:960px;margin:24px auto;padding:0 16px;color:#222}}
h2{{margin-top:32px;border-bottom:2px solid #eee;padding-bottom:4px}}
.card{{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #f0f0f0;align-items:center}}
.card img{{width:72px;height:72px;object-fit:contain;border-radius:6px;background:#fafafa}}
.price{{font-weight:700;font-size:1.1em}} .muted{{color:#666;font-size:.9em}}
.tag{{display:inline-block;background:#eef;padding:1px 6px;border-radius:4px;font-size:.8em;margin-right:4px}}
a{{color:#0a58ca;text-decoration:none}}
nav{{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}}
nav a{{background:#f2f4f8;padding:5px 10px;border-radius:999px;font-size:.85em;color:#222}}</style>
<h1>📊 Radar de Ofertas Tech — {today}</h1><p class="muted">{html.escape(stats)}</p>"""]
    # menu para pular direto para cada seção
    parts.append("<nav>" + "".join(
        f'<a href="#s{i}">{html.escape(title.split(" — ")[0].split(" (")[0])} ({len(items)})</a>'
        for i, (title, items) in enumerate(sections)) + "</nav>")
    for i, (title, items) in enumerate(sections):
        parts.append(f'<h2 id="s{i}">{html.escape(title)}</h2>')
        for p in items:
            img = f'<img src="{html.escape(p.image)}" loading="lazy">' if p.image else '<img alt="">'
            comm = f"{p.commission_rate:.0%}" + (" (estimada)" if p.commission_is_estimate else "")
            drop = f' <span class="tag">⬇️ era {brl(p.previous_price)}</span>' if p.price_drop else ""
            meta = " · ".join(x for x in [
                f"{p.sales} vendidos" if p.sales else "", f"⭐ {p.rating:.1f}" if p.rating else "",
                html.escape(p.shop or "")] if x)
            parts.append(f"""<div class="card">{img}<div>
<a href="{html.escape(p.url)}" target="_blank">{html.escape(p.title)}</a><br>
<span class="price">{brl(p.price)}</span>{drop} <span class="tag">{SOURCE_LABEL[p.source]}</span>
<span class="tag">comissão {comm} ≈ {brl(p.commission_value)}</span><br><span class="muted">{meta}</span>
</div></div>""")
    return "\n".join(parts)


def save_files(products: list[Product], sections, stats: str) -> tuple[Path, Path]:
    out = Path("reports")
    out.mkdir(exist_ok=True)
    day = datetime.date.today().isoformat()
    html_path = out / f"{day}.html"
    html_path.write_text(to_html(sections, stats), encoding="utf-8")
    (out / "latest.html").write_text(to_html(sections, stats), encoding="utf-8")
    (out / "index.html").write_text(to_html(sections, stats), encoding="utf-8")  # página inicial do GitHub Pages
    with open(out / f"{day}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["plataforma", "categoria", "titulo", "preco", "preco_anterior", "comissao_%",
                    "comissao_estimada", "comissao_R$", "vendas", "nota", "novo", "link"])
        for p in sorted(products, key=lambda p: (p.category, p.price)):
            w.writerow([p.source, p.category, p.title, f"{p.price:.2f}".replace(".", ","),
                        f"{p.previous_price:.2f}".replace(".", ",") if p.previous_price else "",
                        f"{p.commission_rate * 100:.1f}".replace(".", ","),
                        "sim" if p.commission_is_estimate else "não",
                        f"{p.commission_value:.2f}".replace(".", ","),
                        p.sales or "", p.rating or "", "sim" if p.is_new else "", p.url])
    return html_path, out / f"{day}.csv"


def send_email(html_body: str, csv_path: Path, total: int) -> bool:
    """Um único e-mail por dia: relatório completo no corpo + planilha com TODOS os produtos anexada."""
    user, pwd, to = (os.getenv(k) for k in ("SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO"))
    if not (user and pwd and to):
        return False
    host = os.getenv("SMTP_HOST") or "smtp.gmail.com"
    port = int(os.getenv("SMTP_PORT") or 587)

    msg = MIMEMultipart()
    msg["Subject"] = f"Radar de Ofertas Tech — {datetime.date.today():%d/%m/%Y} — {total} ofertas"
    msg["From"], msg["To"] = user, to
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    att = MIMEApplication(csv_path.read_bytes(), Name=csv_path.name)
    att["Content-Disposition"] = f'attachment; filename="{csv_path.name}"'
    msg.attach(att)

    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, pwd)
        s.sendmail(user, [a.strip() for a in to.split(",")], msg.as_string())
    return True
