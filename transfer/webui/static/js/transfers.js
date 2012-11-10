function initAddOverlay() {
    $('#overlay_trigger').overlay({
        mask: 'black',
        top: 'center',
        });
    };

function initAdd() {
    $('.button').bind('click', function() {
        $.getJSON($SCRIPT_ROOT + '/transfers/add',
            $(this).parents('form').serializeArray(),
            function(data) {
                if (data.message) {
                    $('#add_message').text(data.message);
                    $('#overlay_trigger').overlay().load();
                    }
                else {
                    location.reload();
                    }
                });

        return false;
        });
    };

function initActions() {
    $('.img_button[alt]').bind('click', function() {
        var action = $(this).attr('alt');
        var div = $(this).parents('.content_element')[0];

        if (action == 'more') {
            $(div).find('.element_more').slideToggle();
            }
        else if (action == 'remove') {
            $.getJSON($SCRIPT_ROOT + '/transfers/cancel',
                {id: $(div).find('input[name="id"]').val()},
                function(data) {
                    if (data.result == true) {
                        $(div).fadeOut();
                        }
                    });
            }

        return false;
        });
    };

function updateTransfer() {
    if (has_focus) {
        $('.content_element').each( function(result) {
            var download = $(this);
            var progressbar = $(this).find('.progressbar');
            var element_more = $(this).find('.element_more');

            $.getJSON($SCRIPT_ROOT + '/transfers/update',
                {id: $(this).find('input[name="id"]').val()},
                function(data) {
                    if (data.name == null) {
                        download.fadeOut();
                        }
                    else {
                        download.find('.name').html(data.name);
                        element_more.find('.progress').html(data.progress);
                        element_more.find('.transferred').html(data.transferred);
                        element_more.find('.size').html(data.size);

                        if (data.progress > 0) {
                            progressbar.width(parseInt(data.progress * 400 / 100));
                            progressbar.show();
                            }
                        else {
                            progressbar.hide();
                            }
                        }
                    });
            });
        }
    };

$(function() {
    initAddOverlay();
    initAdd();
    initActions();
    updateTransfer();
    var progress_interval = window.setInterval(updateTransfer, 5000);
    });
