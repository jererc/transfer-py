var showDelays = {};


function toggleElementNew(element, direction, delay) {
    var id = 'new';
    clearTimeout(showDelays[id]);
    var info = $(element).find('.element-new');
    showDelays[id] = setTimeout(function () {
        if (direction == 'up') {
            info.slideUp('slow', function() {
                $(element).removeClass('element-highlight', 200);
            });
        } else {
            info.slideDown('fast', function() {
                $(element).addClass('element-highlight');
            });
        }
    }, delay);
};

function toggleElement(element, direction, delay) {
    var id = $(element).attr('data-id');
    clearTimeout(showDelays[id]);
    var info = $(element).find('.element-info');
    showDelays[id] = setTimeout(function () {
        if (direction == 'up') {
            info.slideUp('slow');
        } else {
            info.slideDown('fast');
        }
    }, delay);
};

function initActions() {
    $('.content-new').mouseenter(function() {
        $(this).addClass('element-highlight');
        toggleElementNew(this, 'down', 600);
    });
    $('.content-new').mouseleave(function() {
        toggleElementNew(this, 'up', 600);
    });

    $('.content-element').mouseenter(function() {
        $(this).addClass('element-highlight');
        $(this).find('.element-actions').show();
        toggleElement(this, 'down', 600);
    });
    $('.content-element').mouseleave(function() {
        $(this).removeClass('element-highlight');
        $(this).find('.element-actions').hide();
        toggleElement(this, 'up', 2000);
    });

    $('.img-button[alt="add"]').click(function() {
        var div = $(this).parents('.content-new')[0];
        var form = $(div).find('form');
        form.find('.default-text').each(function() {
            if ($(this).val() == this.title) {
                $(this).val("");
            }
        });

        $.getJSON($SCRIPT_ROOT + '/transfers/add',
            form.serializeArray(),
            function(data) {
                if (data.message) {
                    initInputFields();
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
    if (hasFocus) {
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
    }
};

$(function() {
    initActions();
    updateTransfer();
    var progressInterval = window.setInterval(updateTransfer, 5000);
});
