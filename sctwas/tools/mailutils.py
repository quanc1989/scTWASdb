from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.conf import settings


def sendEmail(mailto, info):
    EmailMessage(
        subject='scTWASdb Info',
        body=info,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[mailto]
    ).send()


def sendEmailWithHtml(mailto, info):
    msg = EmailMultiAlternatives(
        subject='scTWASdb Info',
        body=info,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[mailto]
    )
    msg.content_subtype = "html"
    # msg.attach_alternative(info_html, "text/html")
    # msg.attach_alternative(info_html, "text/html")
    msg.send()


def sendEmailWithAttachment(mailto, info, list_attachment):
    email = EmailMessage(
        subject='scTWASdb Result',
        body=info,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[mailto]
    )
    email.content_subtype = "html"
    for path_attachment in list_attachment:
        email.attach_file(path_attachment, mimetype='text/csv')
        # email.attach
    email.send()
