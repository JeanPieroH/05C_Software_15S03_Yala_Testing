import smtplib
import os
import unicodedata
import csv
import xml.etree.ElementTree as ET
import tempfile
from datetime import datetime
import textwrap

from email.message import EmailMessage
from email.header import Header
from email.headerregistry import Address
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from config import (
    SMTP_SERVER,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    EMAIL_FROM,
)

def normalize_text(text: str | None) -> str:
    """
    Reemplaza NBSP (\xa0) por espacio normal y normaliza a NFC.
    Garantiza que el texto sea seguro para encabezados/HTML.
    """
    if not text:
        return ""
    return unicodedata.normalize("NFC", text.replace("\xa0", " "))

def send_email(to_email: str, subject: str, body_html: str, attachments: dict[str, str | bytes] | None = None) -> bool:
    """
    Envía un correo HTML (UTF-8) con adjuntos opcionales.
    - attachments: {nombre_archivo: contenido (str o bytes)}
    """
    subject = normalize_text(subject)
    body_html = normalize_text(body_html)
    to_email = to_email.strip()

    msg = MIMEMultipart('alternative')

    from_user, from_domain = EMAIL_FROM.split("@", 1)
    msg["From"] = f"YALA <{EMAIL_FROM}>"
    msg["To"] = to_email
    msg['Subject'] = Header(subject, 'utf-8')
    
    text_part = MIMEText("Este mensaje requiere un visor HTML.", 'plain', 'utf-8')
    html_part = MIMEText(body_html, 'html', 'utf-8')
    
    msg.attach(text_part)
    msg.attach(html_part)

    if attachments:
        for filename, content in attachments.items():
            if isinstance(content, str):
                content = content.encode("utf-8")

            attachment = MIMEApplication(content)
            attachment.add_header('Content-Disposition', 'attachment', 
                                 filename=normalize_text(filename).encode('utf-8').decode('utf-8'))
            
            if filename.lower().endswith(".csv"):
                attachment.add_header('Content-Type', 'text/csv; charset=utf-8')
            elif filename.lower().endswith(".xml"):
                attachment.add_header('Content-Type', 'application/xml; charset=utf-8')
                
            msg.attach(attachment)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()

            clean_username = normalize_text(SMTP_USERNAME)
            clean_password = normalize_text(SMTP_PASSWORD).replace('\xa0', ' ')
            server.login(clean_username, clean_password)
            message_string = msg.as_string()
            
            server.sendmail(
                from_addr=EMAIL_FROM,
                to_addrs=[to_email],
                msg=message_string
            )
            
            print("Email sent successfully")
        return True

    except UnicodeEncodeError as uee:
        print(f"Unicode Encoding Error: {uee}")
        print(f"Error position: {uee.start}-{uee.end}, object: {repr(uee.object[uee.start:uee.end])}")
        print(f"Complete problematic string: {repr(uee.object)}")
        return False
    except Exception as e:
        print(f"Error de correo: {e}")
        print(f"- Error type: {type(e).__name__}")
        print(f"- Servidor SMTP: {SMTP_SERVER}")
        print(f"- Puerto SMTP: {SMTP_PORT}")
        print(f"- Destinatario: {to_email}")
        return False

def send_welcome_email(to_email: str, user_name: str) -> bool:
    subject = "¡Bienvenido a YALA!"
    body = textwrap.dedent(f"""\
        <html>
          <body>
            <h2>¡Bienvenido a YALA, {user_name}!</h2>
            <p>Tu cuenta ha sido creada exitosamente.</p>
            <p>Ahora puedes comenzar a administrar tus cuentas y realizar transacciones.</p>
            <p>¡Gracias por elegir nuestro servicio!</p>
            <br>
            <p>Saludos cordiales,<br>El Equipo de YALA</p>
          </body>
        </html>
    """)
    return send_email(to_email, subject, body)

def send_transaction_notification(
    to_email: str,
    user_name: str,
    transaction,
    source_currency: str,
    dest_currency: str,
    is_sender: bool = True,
) -> bool:
    action = "enviado" if is_sender else "recibido"
    amount  = transaction.source_amount if is_sender else transaction.destination_amount
    currency = source_currency if is_sender else dest_currency

    subject = f"Notificación de Transacción - {action.capitalize()} {amount} {currency}"
    body = f"""
    <html>
    <body>
        <h2>Notificación de Transacción</h2>
        <p>Estimado/a {user_name},</p>
        <p>Has {action} una transacción:</p>
        <ul>
            <li>Monto: {amount} {currency}</li>
            <li>Fecha: {transaction.timestamp}</li>
            <li>Descripción: {transaction.description or 'Sin descripción'}</li>
        </ul>
        <p>¡Gracias por usar nuestro servicio!</p>
        <br>
        <p>Saludos cordiales,<br>El Equipo de YALA</p>
    </body>
    </html>
    """
    return send_email(to_email, subject, body)

def create_csv_export(user, account, transactions) -> str:
    with tempfile.NamedTemporaryFile(delete=False, mode="w", newline="", suffix=".csv", encoding="utf-8") as tmp:
        w = csv.writer(tmp)
        w.writerow(["Estado de Cuenta"])
        w.writerow([])
        w.writerow(["Usuario", user.full_name])
        w.writerow(["Correo", user.email])
        w.writerow(["ID de Cuenta", account.id])
        w.writerow(["Moneda", account.currency.code])
        w.writerow(["Saldo", account.balance])
        w.writerow(["Fecha de Generación", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        w.writerow([])
        w.writerow(["ID Transacción", "Fecha", "Descripción", "Monto", "Tipo"])

        for tx in transactions:
            outgoing = tx.source_account_id == account.id
            amount   = -tx.source_amount if outgoing else tx.destination_amount
            tx_type  = "Saliente" if outgoing else "Entrante"
            w.writerow([
                tx.id,
                tx.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                tx.description or "",
                amount,
                tx_type,
            ])
    with open(tmp.name, "r", encoding="utf-8") as fh:
        content = fh.read()
    os.unlink(tmp.name)
    return content

def create_xml_export(user, account, transactions) -> bytes:
    root = ET.Element("EstadoDeCuenta")
    user_el = ET.SubElement(root, "Usuario")
    ET.SubElement(user_el, "Nombre").text  = user.full_name
    ET.SubElement(user_el, "Correo").text  = user.email

    acct_el = ET.SubElement(root, "Cuenta")
    ET.SubElement(acct_el, "ID").text     = str(account.id)
    ET.SubElement(acct_el, "Moneda").text = account.currency.code
    ET.SubElement(acct_el, "Saldo").text  = str(account.balance)

    ET.SubElement(root, "FechaGeneracion").text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    txs_el = ET.SubElement(root, "Transacciones")
    for tx in transactions:
        tx_el = ET.SubElement(txs_el, "Transaccion")
        ET.SubElement(tx_el, "ID").text   = str(tx.id)
        ET.SubElement(tx_el, "Fecha").text = tx.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        ET.SubElement(tx_el, "Descripcion").text = tx.description or ""
        outgoing = tx.source_account_id == account.id
        ET.SubElement(tx_el, "Monto").text = str(-tx.source_amount if outgoing else tx.destination_amount)
        ET.SubElement(tx_el, "Tipo").text  = "Saliente" if outgoing else "Entrante"

    return ET.tostring(root, encoding="utf-8", method="xml")

def send_account_statement(to_email, user_name, account, transactions, fmt: str = "csv") -> bool:
    subject = f"Estado de Cuenta - Cuenta en {account.currency.code}"
    body = f"""
    <html>
    <body>
        <h2>Estado de Cuenta</h2>
        <p>Estimado/a {user_name},</p>
        <p>Adjunto encontrarás tu estado de cuenta en formato {fmt.upper()}.</p>
        <p>¡Gracias por usar nuestro servicio!</p>
        <br>
        <p>Saludos cordiales,<br>El Equipo de YALA</p>
    </body>
    </html>
    """

    if fmt.lower() == "csv":
        content  = create_csv_export(account.user, account, transactions)
        filename = f"estado_cuenta_{account.id}_{datetime.now():%Y%m%d}.csv"
    elif fmt.lower() == "xml":
        content  = create_xml_export(account.user, account, transactions)
        filename = f"estado_cuenta_{account.id}_{datetime.now():%Y%m%d}.xml"
    else:
        raise ValueError(f"Formato no soportado: {fmt}")

    return send_email(to_email, subject, body, {filename: content})
