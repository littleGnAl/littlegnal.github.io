window.onload = function() {
    var obtn = document.getElementById('goTop');
    var timer = null;
    var isTop = true;
    var clientHeight = document.documentElement.clientHeight || document.body.clientHeight;

    window.onscroll = function() {
        var osTop = document.documentElement.scrollTop || document.body.scrollTop;
        if (osTop >= clientHeight) {
            obtn.style.display = 'block';
        }else {
            obtn.style.display = 'none';
        }

        if (!isTop) {
            clearInterval(timer);
        }
        isTop = false;
    };

    goTop.onclick = function() {
        timer = setInterval(function() {
            var osTop = document.documentElement.scrollTop || document.body.scrollTop; 
             
            var isSpeed = Math.floor(-osTop / 6);
            document.documentElement.scrollTop = document.body.scrollTop = osTop + isSpeed;

            isTop = true;

            if (osTop == 0) {
                clearInterval(timer);
            }
        }, 30); 
    };
}