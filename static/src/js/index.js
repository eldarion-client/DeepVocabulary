/* global window document */
window.jQuery = window.$ = require('jquery');

const $ = window.$;

require('bootstrap/dist/js/bootstrap.bundle');
require('bootstrap-slider');

import ajaxSendMethod from './ajax';
import handleMessageDismiss from './messages';
import loadStripeElements from './pinax-stripe';
import hookupCustomFileWidget from './pinax-documents';

$(() => {
    $(document).ajaxSend(ajaxSendMethod);

    // Topbar active tab support
    $('.topbar li').removeClass('active');

    const classList = $('body').attr('class').split(/\s+/);
    $.each(classList, (index, item) => {
        const selector = `ul.nav li#tab_${item}`;
        $(selector).addClass('active');
    });

    $('#account_logout, .account_logout').click(e => {
        e.preventDefault();
        $('#accountLogOutForm').submit();
    });

    $('#ex12c').slider({
      id: 'slider12c',
      min: 0,
      max: 10,
      range: true,
      value: [3, 7],
    });

    handleMessageDismiss();
    loadStripeElements();
    hookupCustomFileWidget();
});
