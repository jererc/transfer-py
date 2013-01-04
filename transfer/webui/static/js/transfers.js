function initAddOverlay() {
    $('#overlay_trigger').overlay({
        mask: 'black',
        top: 'center',
    });
};

function initActions() {
    $('.content_element').mouseover(function() {
        $(this).addClass('element_highlight');
        $(this).find('.element_actions').show();
    });
    $('.content_element').mouseleave(function() {
        $(this).removeClass('element_highlight');
        $(this).find('.element_actions').hide();
    });

    $('.img_button[alt="add"]').mouseover(function() {
        var content = $(this).parents('.content_new')[0];
        $(content).addClass('element_highlight', 200);
        $(content).find('.element_new').slideDown('fast');
    });
    $('.content_new').mouseleave(function() {
        $(this).find('.element_new').slideUp('slow', function() {
            $('.content_new').removeClass('element_highlight', 200);
        });
    });

    $('.img_button[alt="add"]').bind('click', function() {
        var div = $(this).parents('.content_new')[0];
        $.getJSON($SCRIPT_ROOT + '/transfers/add',
            $(div).find('form').serializeArray(),
            function(data) {
                if (data.message) {
                    $('.add_message').text(data.message);
                    $('#overlay_trigger').overlay().load();
                } else {
                    location.reload();
                }
            });
        return false;
    });

    $('.img_button[alt="more"]').bind('click', function() {
        var div = $(this).parents('.content_element')[0];
        $(div).find('.element_info').slideToggle('fast');
        return false;
    });

    $('.img_button[alt="remove"]').bind('click', function() {
        var div = $(this).parents('.content_element')[0];
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
        $('.content_element').each(function(result) {
            var download = $(this);
            var progressBar = $(this).find('.progressbar');
            var contentInfo = $(this).find('.element_info');

            $.getJSON($SCRIPT_ROOT + '/transfers/update',
                {id: $(this).find('input[name="id"]').val()},
                function(data) {
                    if (data.name == null) {
                        download.fadeOut();
                    } else {
                        download.find('.name').html(data.name);
                        contentInfo.find('.progress').html(data.progress);
                        contentInfo.find('.transferred').html(data.transferred);
                        contentInfo.find('.size').html(data.size);

                        if (data.progress > 0) {
                            var width_total = download.find('.progress').width();
                            progressBar.width(parseInt(data.progress * width_total / 100));
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
    initAddOverlay();
    initActions();
    updateTransfer();
    var progressInterval = window.setInterval(updateTransfer, 5000);
});
