var isMobile = isMobile();
var hasFocus = true;


function isMobile() {
    if (navigator.userAgent.match(/iPhone|iPod|iPad|Android|WebOS|Blackberry|Symbian|Bada/i)) {
        return true;
    } else {
        return false;
    }
};

function handleFocus() {
    $(window).blur(function() {
        hasFocus = false;
    });
    $(window).focus(function() {
        hasFocus = true;
    });
};

$(function() {
    if (isMobile) {
        $('body').addClass('wide');
    }
    handleFocus();
});
