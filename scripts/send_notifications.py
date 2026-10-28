"""Send pending ODJ notification emails via SMTP when explicitly enabled.

Usage:
 python scripts/send_notifications.py            # count pending, safe no-op
 python scripts/send_notifications.py --send     # SMTP required; sends in small batch
 Run --send periodically with a trusted task scheduler once configured.
"""
from pathlib import Path
import sys, os, smtplib, ssl, argparse
from email.message import EmailMessage
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1]/'.env')
from sqlalchemy import select
from database import create_tables, SessionLocal, EmailOutbox, now

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--send',action='store_true',help='Actually deliver queued messages')
    args=parser.parse_args();create_tables()
    with SessionLocal() as db:
        pending=db.scalars(select(EmailOutbox).where(EmailOutbox.status=='pending').order_by(EmailOutbox.id).limit(20)).all()
        print('Pending messages (up to 20):',len(pending))
        if not args.send:
            print('No emails sent. Add --send when SMTP is configured.');return
        if not pending: return
        host=os.getenv('SMTP_HOST',''); username=os.getenv('SMTP_USERNAME','');password=os.getenv('SMTP_PASSWORD','');sender=os.getenv('SMTP_FROM','')
        port=int(os.getenv('SMTP_PORT','587'))
        if not (host and username and password and sender and port==587):
            raise SystemExit('SMTP delivery requires SMTP_HOST, SMTP_PORT=587, SMTP_USERNAME, SMTP_PASSWORD and SMTP_FROM in private .env.')
        # STARTTLS strictly required. Fail closed on unsupported or refused TLS.
        with smtplib.SMTP(host,port,timeout=20) as server:
            server.ehlo();server.starttls(context=ssl.create_default_context());server.ehlo();server.login(username,password)
            for message in pending:
                mail=EmailMessage();mail['From']=sender;mail['To']=message.recipient;mail['Subject']=message.subject
                mail.set_content(message.text_body);mail.add_alternative(message.html_body,subtype='html')
                server.send_message(mail)
                message.status='sent';message.sent_at=now();db.commit()
                print('Sent notification',message.id,message.kind)

if __name__=='__main__':main()
