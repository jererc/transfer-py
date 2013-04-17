var slideDelays = {};
var isMobile = isMobile();
var hasFocus = true;


//
// Tools
//
function slideDelay(id, element, direction, delay) {
    clearTimeout(slideDelays[id]);
    if (!element) {
        return false;
    }
    slideDelays[id] = setTimeout(function() {
        if (direction == 'up') {
            element.stop(true);
            element.slideUp(100);
        } else {
            element.stop(true);
            element.slideDown(150);
        }
    }, delay);
};

function isMobile() {
    if (navigator.userAgent.match(/iPhone|iPod|iPad|Android|WebOS|Blackberry|Symbian|Bada/i)) {
        return true;
    } else {
        return false;
    }
};


//
// Init
//
function setFontSize() {
    if (!isMobile) {
        var size = screen.width;
        var ratio = 1;
    } else {
        if ($(window).width() > $(window).height()) {
            var size = Math.max(screen.width, screen.height);
            var ratio = 1.5;
        } else {
            var size = Math.min(screen.width, screen.height);
            var ratio = 3;
        }
    }
    if (size >= 1920) {
        var percent = 100;
    } else if (size >= 1600) {
        var percent = 80;
    } else if (size >= 1280) {
        var percent = 62.5;
    } else {
        var percent = 50;
    }
    $('body').css('font-size', ratio * percent + '%');
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
    setFontSize();
    handleFocus();
});
