var showDelays = {};


function toggleElement(id, element, direction, delay) {
    clearTimeout(showDelays[id]);
    if (!element) {
        return false;
    }
    showDelays[id] = setTimeout(function() {
        if (direction == 'up') {
            element.slideUp(300);
        } else {
            element.slideDown(100);
        }
    }, delay);
};

function initActions() {
    $('.content-new-trigger, .content-new').mouseenter(function() {
        toggleElement('new', $('.content-new'), 'down', 500);
    });
    $('.content-new-trigger').mouseleave(function() {
        toggleElement('new');
    });
    $('.content-new').mouseleave(function() {
        toggleElement('new', $(this), 'up', 600);
    });

    $('.content-element').mouseenter(function() {
        $(this).addClass('element-highlight');
        toggleElement($(this).attr('data-id'),
                $(this).find('.element-info'), 'down', 600);
    });
    $('.content-element').mouseleave(function() {
        $(this).removeClass('element-highlight');
        toggleElement($(this).attr('data-id'),
                $(this).find('.element-info'), 'up', 2000);
    });

    if (isMobile) {
        $('.element-actions').each(function() {
            $(this).show();
        });
    } else {
        $('.content-element').mouseenter(function() {
            $(this).find('.element-actions').show();
        });
        $('.content-element').mouseleave(function() {
            $(this).find('.element-actions').hide();
        });
    }

    $('.img-button[alt="add"]').click(function() {
        var div = $(this).parents('.content-new')[0];
        var form = $(div).find('form');
        $.getJSON($SCRIPT_ROOT + '/transfers/add',
            form.serializeArray(),
            function(data) {
                if (data.message) {
                    $('.add-message').text(data.message);
                } else {
                    location.reload();
                }
            });
        return false;
    });

    $('.img-button[alt="remove"]').click(function() {
        var div = $(this).parents('.content-element')[0];
        $.getJSON($SCRIPT_ROOT + '/transfers/cancel',
            {id: $(div).find('input[name="id"]').val()},
            function(data) {
                if (data.result == true) {
                    $(div).fadeOut();
                }
            });
        return false;
    });
};

function updateTransfer() {
    if (!hasFocus) {
        return false;
    }
    $('.content-element').each(function(result) {
        var download = $(this);
        var progressBar = $(this).find('.progressbar');
        var contentInfo = $(this).find('.element-info');

        $.getJSON($SCRIPT_ROOT + '/transfers/update',
            {id: $(this).find('input[name="id"]').val()},
            function(data) {
                if (data.name == null) {
                    download.fadeOut();
                } else {
                    download.find('.transfer-name').html(data.name);
                    contentInfo.find('.transfer-progress').html(data.progress);
                    contentInfo.find('.transfer-transferred').html(data.transferred);
                    contentInfo.find('.transfer-size').html(data.size);
                    contentInfo.find('.transfer-rate').html(data.transfer_rate);

                    if (data.progress > 0) {
                        var widthTotal = download.find('.progress').width();
                        progressBar.width(parseInt(data.progress * widthTotal / 100));
                        progressBar.show();
                    } else {
                        progressBar.hide();
                    }
                }
            });
    });
};

$(function() {
    initActions();
    updateTransfer();
    var progressInterval = window.setInterval(updateTransfer, 5000);
});
