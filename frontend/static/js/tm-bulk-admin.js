
(() => {
'use strict';

const sidebar = document.querySelector('.admin-sidebar');
const main = document.querySelector('.admin-main');
if (!sidebar || !main || document.getElementById('tab-wholesale')) return;

const button = document.createElement('button');
button.type = 'button';
button.className = 'side-nav';
button.dataset.tab = 'wholesale';
button.textContent = '✉   Wholesale inquiries';

const settings = sidebar.querySelector('[data-tab="settings"]');

if (settings) settings.before(button);
else sidebar.appendChild(button);

const section = document.createElement('section');
section.className = 'admin-tab';
section.id = 'tab-wholesale';
section.hidden = true;

const toolbar = document.createElement('div');
toolbar.className = 'admin-section-toolbar';

const heading = document.createElement('div');
heading.innerHTML =
    '<h2>Wholesale inquiries</h2>' +
    '<p>Saved bulk pricing requests. Reply using your business email.</p>';

const refresh = document.createElement('button');
refresh.type = 'button';
refresh.className = 'btn btn-outline';
refresh.textContent = 'Refresh requests';

toolbar.append(heading, refresh);

const inbox = document.createElement('div');
inbox.className = 'tm-wholesale-inbox';
inbox.setAttribute('aria-live', 'polite');

section.append(toolbar, inbox);
main.appendChild(section);

const text = (tag, value) => {
    const el = document.createElement(tag);
    el.textContent = value;
    return el;
};


function renderReply(item, article) {
    if (item.reply_status) {
        const state = item.reply_status === 'sent'
            ? 'Reply sent from TrueMerit'
            : 'Reply queued for TrueMerit email';
        const label = text('p', state);
        label.className = 'tm-wholesale-reply-state';
        article.appendChild(label);
        return;
    }

    const open = document.createElement('button');
    open.type = 'button';
    open.className = 'tm-wholesale-reply-open';
    open.innerHTML = 'Reply to inquiry <svg class="tm-arrow-icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19 19 5M9 5h10v10"/></svg>';
    open.setAttribute('aria-expanded', 'false');

    const form = document.createElement('form');
    form.className = 'tm-wholesale-reply-form';
    form.hidden = true;

    const summary = text(
        'p', 'Reply from TrueMerit to ' + item.email +
        '. The customer can respond to your store contact email.'
    );
    summary.className = 'tm-wholesale-reply-help';
    const subject = text(
        'p', 'Subject: Re: TrueMerit bulk pricing request #' + item.id
    );
    subject.className = 'tm-wholesale-reply-subject';

    const label = document.createElement('label');
    label.textContent = 'Your email reply';
    const message = document.createElement('textarea');
    message.name = 'message';
    message.rows = 7;
    message.maxLength = 4000;
    message.minLength = 20;
    message.required = true;
    message.value = [
        'Hello,',
        '',
        'Thank you for contacting TrueMerit Cleaning Supplies about ' +
            item.product_name + ' (' + item.quantity + ' units).',
        '',
        'We appreciate your interest and are reviewing availability and pricing. ' +
            'We will follow up with the details and next steps.',
        '',
        'Best regards,',
        'TrueMerit Cleaning Supplies'
    ].join('\n');
    label.appendChild(message);

    const notice = text(
        'p', 'Review the draft and add the correct prices or availability ' +
        'before sending. Pricing is never calculated automatically.'
    );
    notice.className = 'tm-wholesale-reply-help';

    const actions = document.createElement('div');
    actions.className = 'tm-wholesale-reply-actions';
    const send = document.createElement('button');
    send.type = 'submit';
    send.className = 'tm-wholesale-reply-send';
    send.textContent = 'Queue email reply';
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.className = 'tm-wholesale-reply-cancel';
    cancel.textContent = 'Cancel';
    actions.append(send, cancel);

    const feedback = document.createElement('p');
    feedback.className = 'tm-wholesale-reply-feedback';
    feedback.setAttribute('role', 'status');
    feedback.setAttribute('aria-live', 'polite');

    form.append(summary, subject, label, notice, actions, feedback);
    article.append(open, form);

    const toggle = (expanded) => {
        form.hidden = !expanded;
        open.setAttribute('aria-expanded', String(expanded));
        if (expanded) message.focus();
    };
    open.addEventListener('click', () => toggle(form.hidden));
    cancel.addEventListener('click', () => toggle(false));

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!message.reportValidity()) return;
        send.disabled = true;
        cancel.disabled = true;
        feedback.textContent = 'Queueing the TrueMerit email…';

        try {
            const response = await fetch(
                '/api/admin/wholesale-inquiries/' + encodeURIComponent(item.id) + '/reply',
                {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: message.value})
                }
            );
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw Error(data.detail || 'Could not queue the reply.');
            }
            feedback.textContent = 'Reply queued. Your TrueMerit email sender will deliver it.';
            await load();
        } catch (err) {
            feedback.textContent = err.message;
            send.disabled = false;
            cancel.disabled = false;
        }
    });
}

async function load() {
    inbox.replaceChildren(text('p', 'Loading inquiries…'));

    try {
        const response = await fetch(
            '/api/admin/wholesale-inquiries',
            {credentials: 'same-origin'}
        );

        const data = await response.json().catch(() => null);

        if (!response.ok || !Array.isArray(data)) {
            throw Error('Could not load inquiries.');
        }

        inbox.replaceChildren();

        if (!data.length) {
            inbox.appendChild(text('p', 'No wholesale inquiries yet.'));
            return;
        }

        for (const item of data) {
            const article = document.createElement('article');
            article.className = 'tm-wholesale-entry';

            article.appendChild(
                text('h3', item.business_name + ' · #' + item.id)
            );
            article.appendChild(
                text('p', item.product_name + ' · ' + item.quantity + ' units')
            );
            article.appendChild(text('p', 'Email: ' + item.email));
            article.appendChild(
                text('p', 'Submitted: ' +
                    new Date(item.created_at).toLocaleString())
            );

            if (item.notes) {
                article.appendChild(text('p', 'Notes: ' + item.notes));
            }

            renderReply(item, article);
            inbox.appendChild(article);
        }

    } catch (err) {
        inbox.replaceChildren(text('p', err.message));
    }
}

button.addEventListener('click', () => {
    document.querySelectorAll('.admin-tab')
        .forEach(el => el.hidden = el !== section);

    document.querySelectorAll('.side-nav')
        .forEach(el => el.classList.toggle('selected', el === button));

    const title = document.getElementById('tab-title');
    if (title) title.textContent = 'Wholesale inquiries';

    const subtitle = document.getElementById('tab-subtitle');
    if (subtitle) {
        subtitle.textContent = 'Review requests for business pricing.';
    }

    load();
});

refresh.addEventListener('click', load);
})();
