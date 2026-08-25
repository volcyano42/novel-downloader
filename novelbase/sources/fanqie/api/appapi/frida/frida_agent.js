// frida agent：章节代理（hook 拦截器改 item_id + CryptManager 抓明文）
// 配合 Python 端 chapter_content_frida() 使用。
// 加载方式：frida -H 127.0.0.1:27042 -f com.dragon.read -l frida_agent.js（或 Python attach 注入）
var targetItem = null;
var targetBook = null;
var dk_b = null;

function setup() {
    try { Java.perform(function () { send({ready: true}); }); }
    catch (e) { setTimeout(setup, 1000); }
}
setup();

setTimeout(function () {
    Java.perform(function () {
        // 1. hook RealInterceptorChain.proceed：reader/full 请求改写 item_id/book_id
        try {
            var RIC = Java.use("okhttp3.internal.http.RealInterceptorChain");
            RIC.proceed.overloads.forEach(function (ov) {
                ov.implementation = function () {
                    var args = Array.prototype.slice.call(arguments);
                    try {
                        var req = args[args.length - 1];
                        if (!req || typeof req.url !== "function") return ov.apply(this, args);
                        var url = req.url().toString();
                        if (targetItem && url.indexOf("reader/full") >= 0) {
                            var newUrl = url.replace(/item_id=\d+/, "item_id=" + targetItem);
                            if (targetBook) newUrl = newUrl.replace(/book_id=\d+/, "book_id=" + targetBook);
                            var builder = req.newBuilder();
                            builder.url(Java.use("okhttp3.HttpUrl").parse(newUrl));
                            try { builder.tag(req.tag()); } catch (e) {}
                            req = builder.build();
                            args[args.length - 1] = req;
                            send({chapter_target: targetItem});
                            targetItem = null;
                            targetBook = null;
                        }
                    } catch (e) { send({proxy_err: String(e)}); }
                    return ov.apply(this, args);
                };
            });
        } catch (e) { send({ric_err: String(e)}); }

        // 2. hook CryptManager.decrypt：抓 gzip 明文
        try {
            var CM = Java.use("com.dragon.read.crypt.CryptManager");
            CM.decrypt.overloads.forEach(function (ov) {
                ov.implementation = function () {
                    var r = ov.apply(this, arguments);
                    try {
                        if (r != null && r.length > 300) {
                            var b64 = Java.use("android.util.Base64").encodeToString(r, 0);
                            send({chapter_gzip: r.length, gz_b64: b64});
                        }
                    } catch (e) {}
                    return r;
                };
            });
        } catch (e) { send({cm_err: String(e)}); }

        // 3. hook DecryptKey：记录会话密钥（备用）
        try {
            var DK = Java.use("com.dragon.read.reader.DecryptKey");
            DK.$init.overloads.forEach(function (ov) {
                ov.implementation = function () {
                    var r = ov.apply(this, arguments);
                    try { dk_b = String(arguments[1]); } catch (e) {}
                    return r;
                };
            });
        } catch (e) {}

        send({hooked: true});
    });
}, 3000);

recv("target", function (msg) {
    var req = msg.payload || msg;
    targetItem = req.item_id;
    targetBook = req.book_id;
    send({target_ok: true});
});
recv("getkey", function (msg) {
    send({key: dk_b});
});
