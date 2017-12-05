function patchew_api_do(method, data)
{
    data = {params: JSON.stringify(data)};
    console.log(data);
    return $.post("/api/" + method + "/", data);
}
function patchew_toggler_onclick(which)
{
    tgt = $(which).parent().find(".panel-toggle");
    tgt.toggle();
    url = tgt.attr("data-content-url");
    if (tgt.find(".progress-bar") && url) {
        $.get(url, function (data) {
            tgt.html("<pre>" + data + "</pre>");
        });
    }
}
function add_fixed_scroll_events()
{
    $(window).scroll(function() {
        var pre_fixed = $('#pre-fixed');
        var fixed = $('#fixed');
        // add/remove the col-lg-NN attribute to the #fixed element, because
        // "position: fixed" computes the element's width according to the document's
        fixed.toggleClass('fixed ' + fixed.parent().attr('class'),
                          $(window).scrollTop() >= pre_fixed.offset().top + pre_fixed.height());
    })
}
