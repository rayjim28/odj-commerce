
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

            const reply = document.createElement('a');
            reply.href = 'mailto:' + item.email + '?subject=' +
                encodeURIComponent(
                    'TrueMerit bulk pricing request #' + item.id
                );
            reply.textContent = 'Reply to inquiry ↗';

            article.appendChild(reply);
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
