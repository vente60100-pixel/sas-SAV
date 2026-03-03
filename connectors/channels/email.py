"""
OKTAGON SAV v11.0 — Connecteur Email (IMAP/SMTP)
Vision complète : lit LUS + NON LUS, HTML, nom expéditeur, CC, pièces jointes, SPAM.
"""
import imaplib
import smtplib
import email
import html as _html
import re as _re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from connectors.channels.base import ChannelConnector, IncomingMessage
from logger import logger


class EmailConnector(ChannelConnector):
    """Connecteur Email via IMAP (lecture) et SMTP (envoi)."""

    def __init__(self, address: str, password: str,
                 imap_host: str = 'imap.gmail.com', smtp_host: str = 'smtp.gmail.com',
                 smtp_port: int = 587):
        self.address = address
        self.password = password
        self.imap_host = imap_host
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self._seen_ids: dict = {}  # Message-IDs déjà traités (OrderedDict pour ordre chronologique)

    async def fetch_messages(self) -> list[IncomingMessage]:
        """Fetch emails via IMAP (exécuté dans un thread)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync)

    def _fetch_sync(self) -> list[IncomingMessage]:
        """Fetch synchrone IMAP — lit TOUS les emails (lus + non lus) des dernières 24h."""
        messages = []
        try:
            mail = imaplib.IMAP4_SSL(self.imap_host, timeout=15)
            mail.login(self.address, self.password)

            # Date limite : dernières 48h (rattraper le retard)
            since_date = (datetime.now() - timedelta(hours=48)).strftime('%d-%b-%Y')

            # Scanner INBOX + SPAM
            for folder in ['INBOX', '[Gmail]/Spam']:
                try:
                    status, _ = mail.select(folder)
                    if status != 'OK':
                        continue
                except (UnicodeDecodeError, ValueError, KeyError):
                    continue

                # Chercher TOUS les emails des dernières 24h (lus ET non lus)
                _, data = mail.search(None, f'SINCE {since_date}')
                if not data[0]:
                    continue

                for num in data[0].split():
                    try:
                        # D'abord vérifier le Message-ID sans marquer comme lu
                        _, peek_data = mail.fetch(num, '(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])')
                        if peek_data and peek_data[0] and isinstance(peek_data[0], tuple):
                            mid_raw = peek_data[0][1].decode('utf-8', errors='ignore').strip()
                            mid = mid_raw.replace('Message-ID:', '').replace('Message-Id:', '').strip()
                            if mid and mid in self._seen_ids:
                                continue

                        _, msg_data = mail.fetch(num, '(RFC822)')
                        raw = msg_data[0][1]
                        msg = email.message_from_bytes(raw)

                        from_header = self._decode_header(msg.get('From', ''))
                        # Extraire email ET nom de "Nom <email@domain.com>"
                        email_match = email.utils.parseaddr(from_header)
                        sender_name = email_match[0] or ''
                        email_from = email_match[1].lower() if email_match[1] else from_header.lower()

                        subject = self._decode_header(msg.get('Subject', ''))
                        body = self._get_body(msg)
                        message_id = msg.get('Message-ID', '')
                        in_reply_to = msg.get('In-Reply-To', '')
                        references = msg.get('References', '')

                        # CC
                        cc_header = self._decode_header(msg.get('Cc', '') or msg.get('CC', '') or '')

                        # Pièces jointes — noms et types
                        attachment_names = []
                        if msg.is_multipart():
                            for part in msg.walk():
                                cd = part.get('Content-Disposition', '')
                                if cd and 'attachment' in cd.lower():
                                    fname = part.get_filename()
                                    if fname:
                                        fname = self._decode_header(fname)
                                        attachment_names.append(fname)
                                elif part.get_content_maintype() == 'image' and part.get_filename():
                                    fname = self._decode_header(part.get_filename())
                                    attachment_names.append(fname)

                        headers = {}
                        for key in ['Auto-Submitted', 'X-Auto-Response-Suppress', 'Precedence',
                                    'X-Mailer', 'Content-Type', 'Return-Path']:
                            val = msg.get(key)
                            if val:
                                headers[key] = val

                        messages.append(IncomingMessage(
                            sender=email_from,
                            sender_name=sender_name,
                            subject=subject,
                            body=body,
                            message_id=message_id,
                            in_reply_to=in_reply_to if in_reply_to else None,
                            references=references if references else None,
                            headers=headers,
                            raw_content=raw.decode('utf-8', errors='ignore')[:5000],
                            channel='email',
                            cc=cc_header,
                            attachment_names=attachment_names
                        ))
                        # Tracker ce message_id
                        if message_id:
                            self._seen_ids[message_id] = True
                            if len(self._seen_ids) > 2000:
                                # Garder les 1000 plus récents (dict garde l'ordre d'insertion)
                                keys = list(self._seen_ids.keys())
                                self._seen_ids = {k: True for k in keys[-1000:]}
                    except (UnicodeDecodeError, ValueError, KeyError):
                        continue

            mail.logout()
        except (OSError, imaplib.IMAP4.error) as e:
            logger.error(f'Erreur IMAP fetch: {e}', extra={'action': 'imap_error'})
        return messages

    def _decode_header(self, header: str) -> str:
        """Décode un header email."""
        try:
            parts = decode_header(header)
            return ''.join(
                part.decode(enc or 'utf-8') if isinstance(part, bytes) else part
                for part, enc in parts
            )
        except (UnicodeDecodeError, ValueError, KeyError):
            return header

    def _get_body(self, msg) -> str:
        """Extrait le corps texte d'un email.
        Priorité : text/plain > text/html converti en texte."""
        text_body = None
        html_body = None

        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == 'text/plain' and text_body is None:
                    try:
                        text_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except (UnicodeDecodeError, ValueError, KeyError):
                        pass
                elif ctype == 'text/html' and html_body is None:
                    try:
                        html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except (UnicodeDecodeError, ValueError, KeyError):
                        pass
        else:
            ctype = msg.get_content_type()
            try:
                payload = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                if ctype == 'text/plain':
                    text_body = payload
                elif ctype == 'text/html':
                    html_body = payload
                else:
                    text_body = payload
            except (UnicodeDecodeError, ValueError, KeyError):
                pass

        if text_body and text_body.strip():
            return text_body

        if html_body and html_body.strip():
            return self._html_to_text(html_body)

        return ""

    @staticmethod
    def _html_to_text(html: str) -> str:
        """Convertit du HTML en texte lisible (sans dépendance externe)."""
        text = html
        text = _re.sub(r'<br\s*/?>', '\n', text, flags=_re.IGNORECASE)
        text = _re.sub(r'</(p|div|tr|li|h[1-6])>', '\n', text, flags=_re.IGNORECASE)
        text = _re.sub(r'<(p|div|tr|li|h[1-6])[^>]*>', '', text, flags=_re.IGNORECASE)
        # Extraire le texte des liens
        text = _re.sub(r'<a[^>]*href=["\x27]([^"\x27]*)["\x27][^>]*>(.*?)</a>', r'\2 (\1)', text, flags=_re.IGNORECASE)
        text = _re.sub(r'<style[^>]*>.*?</style>', '', text, flags=_re.IGNORECASE | _re.DOTALL)
        text = _re.sub(r'<script[^>]*>.*?</script>', '', text, flags=_re.IGNORECASE | _re.DOTALL)
        text = _re.sub(r'<[^>]+>', '', text)
        # v9.0 — html.unescape() remplace les .replace() manuels
        text = _html.unescape(text)
        text = text.replace('\xa0', ' ')  # &nbsp; en unicode
        text = _re.sub(r'[ \t]+', ' ', text)
        text = _re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        return text.strip()

    async def send_message(self, to: str, subject: str, html_body: str,
                           in_reply_to: Optional[str] = None) -> bool:
        """Envoie un email via SMTP (exécuté dans un thread)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._send_sync, to, subject, html_body, in_reply_to)

    def _send_sync(self, to: str, subject: str, html_body: str,
                   in_reply_to: Optional[str] = None) -> bool:
        """Envoi synchrone SMTP."""
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.address
            msg['To'] = to
            msg['Subject'] = subject
            if in_reply_to:
                msg['In-Reply-To'] = in_reply_to
                msg['References'] = in_reply_to
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.address, self.password)
                server.sendmail(self.address, to, msg.as_string())
            return True
        except (OSError, smtplib.SMTPException) as e:
            logger.error(f'Erreur SMTP send to {to}: {e}', extra={'action': 'smtp_error'})
            return False
