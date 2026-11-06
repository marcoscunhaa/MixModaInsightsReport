"""Guarda a última análise gerada para reabrir o dashboard sem reprocessar planilhas.

Dois arquivos na pasta de dados:

- ``ultima_analise.json``: resumo pequeno (período, lojas, totais). É o único lido
  ao abrir o app, sem importar pandas, então a tela inicial continua instantânea.
- ``ultima_analise.pkl``: o DataFrame completo, a auditoria e o período. O pickle
  preserva exatamente os tipos da análise (listas de preços, infinito na
  cobertura, códigos como texto), coisa que JSON ou Excel perderiam, e carrega
  em milissegundos.

A gravação do arquivo grande roda numa thread para não travar a tela; os dois
arquivos são escritos de forma atômica (temporário + replace), então um app
fechado no meio da gravação nunca deixa um arquivo pela metade.
"""
import json
import os
import pickle
import tempfile
import threading
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

FORMAT_VERSION = 1
META_NAME = "ultima_analise.json"
DATA_NAME = "ultima_analise.pkl"


class LastAnalysisError(Exception):
    """A última análise não pode ser aberta; a mensagem explica o motivo ao usuário."""


def _atomic_write_bytes(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _iso(value):
    return value.isoformat() if isinstance(value, (date, datetime)) else str(value)


def _parse_day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def describe_period(meta):
    """'01/10 a 31/10/2026' no mesmo ano; datas completas quando os anos diferem."""
    start, end = _parse_day(meta.get("data_inicio")), _parse_day(meta.get("data_fim"))
    if not start or not end:
        return "Período não informado"
    if start == end:
        return end.strftime("%d/%m/%Y")
    first = start.strftime("%d/%m") if start.year == end.year else start.strftime("%d/%m/%Y")
    return f"{first} a {end.strftime('%d/%m/%Y')}"


def describe_saved_at(meta, now=None):
    """'hoje às 14:05', 'ontem às 09:12' ou '03/11/2026 às 18:40'."""
    try:
        saved = datetime.fromisoformat(str(meta.get("salva_em")))
    except ValueError:
        return "data desconhecida"
    days = ((now or datetime.now()).date() - saved.date()).days
    hour = saved.strftime("%H:%M")
    if days == 0:
        return f"hoje às {hour}"
    if days == 1:
        return f"ontem às {hour}"
    return f"{saved.strftime('%d/%m/%Y')} às {hour}"


def summarize(frame, period, stores, saved_at=None):
    """Resumo mostrado no card da tela inicial (somas simples, sem copiar o DataFrame)."""
    from core.stores import order_stores

    def total(column):
        return float(frame[column].sum()) if column in frame else 0.0

    ordered = order_stores(dict.fromkeys(str(store) for store in stores))
    return {
        "version": FORMAT_VERSION,
        "id": uuid4().hex,
        "salva_em": (saved_at or datetime.now()).isoformat(timespec="seconds"),
        "data_inicio": _iso(period[0]),
        "data_fim": _iso(period[1]),
        "lojas": ordered,
        "produtos": int(len(frame)),
        "faturamento": total("valor_vendido"),
        "unidades_vendidas": total("quantidade_vendida"),
        "valor_estoque": total("valor_estoque"),
    }


class LastAnalysisStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.meta_path = self.directory / META_NAME
        self.data_path = self.directory / DATA_NAME
        self._lock = threading.Lock()
        self._writer = None

    # ----- leitura ---------------------------------------------------------
    def meta(self):
        """Resumo da última análise ou None se não houver uma completa salva."""
        try:
            with self.meta_path.open(encoding="utf-8") as stream:
                meta = json.load(stream)
        except (OSError, ValueError):
            return None
        if not isinstance(meta, dict) or not meta.get("id") or not self.data_path.exists():
            return None
        return meta

    def load(self):
        """Devolve (frame, período, auditoria, resumo). Levanta LastAnalysisError se não der."""
        self.wait()  # se uma gravação ainda está em andamento, espera ela terminar
        meta = self.meta()
        if meta is None:
            raise LastAnalysisError("Nenhuma análise salva foi encontrada.")
        if meta.get("version") != FORMAT_VERSION:
            raise LastAnalysisError(
                "A última análise foi salva por outra versão do aplicativo. Gere uma nova análise."
            )
        try:
            with self.data_path.open("rb") as stream:
                payload = pickle.load(stream)
            frame, period, audit = payload["frame"], payload["period"], payload["audit"]
        except Exception as error:  # arquivo apagado, corrompido ou de outra versão do pandas
            raise LastAnalysisError(
                "Não foi possível ler a última análise salva. Gere uma nova análise.\n\n"
                f"{type(error).__name__}: {error}"
            ) from error
        if payload.get("id") != meta["id"]:
            raise LastAnalysisError(
                "Os arquivos da última análise não conferem entre si. Gere uma nova análise."
            )
        return frame, tuple(period), audit, meta

    # ----- gravação --------------------------------------------------------
    def save(self, frame, period, audit, stores, background=True):
        """Salva a análise e devolve o resumo na hora (para atualizar a tela inicial).

        O pickle é montado aqui, na thread principal, para capturar o DataFrame
        exatamente como foi gerado; só a escrita em disco vai para a thread.
        """
        meta = summarize(frame, period, stores)
        payload = pickle.dumps(
            {"version": FORMAT_VERSION, "id": meta["id"], "frame": frame,
             "period": tuple(period), "audit": audit},
            protocol=pickle.HIGHEST_PROTOCOL,
        )
        meta_bytes = (json.dumps(meta, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

        def write():
            with self._lock:
                try:
                    # Dados primeiro, resumo depois: o resumo só existe com os dados completos.
                    _atomic_write_bytes(self.data_path, payload)
                    _atomic_write_bytes(self.meta_path, meta_bytes)
                except OSError as error:
                    print(f"Não foi possível salvar a última análise: {error}")

        if background:
            # Não é daemon: se o app fechar logo após gerar, a gravação termina antes de sair.
            self._writer = threading.Thread(target=write, name="save-last-analysis")
            self._writer.start()
        else:
            write()
        return meta

    def wait(self):
        writer = self._writer
        if writer is not None and writer.is_alive():
            writer.join()
