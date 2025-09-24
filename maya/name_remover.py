# -*- coding: utf-8 -*-
import maya.cmds as cmds
import re

WIN = "BulkRemoveFromNamesWin"

DEFAULT_DEFORMER_BLACKLIST = {
    'skinCluster','blendShape','cluster','lattice','ffd','nonLinear','deltaMush','wire','sculpt','softMod','wrap','tweak',
    'groupParts','groupId',
}
SAFETY_BLACKLIST = {'shadingEngine','materialInfo'}

def _is_referenced(node):
    try:
        return cmds.referenceQuery(node, isNodeReferenced=True)
    except:
        return False

def _short_dag_name(path):
    return path.split("|")[-1]

def _split_namespace(name):
    if ':' in name:
        ns, base = name.rsplit(':', 1)
        return ns, base
    return '', name

def _to_node_names(things):
    if not things: return []
    nodes = cmds.ls(things, objectsOnly=True) or []
    clean = []
    for n in nodes:
        if not cmds.objExists(n): continue
        if "." in n or "[" in n or "]" in n:  # 属性/要素表記除外
            continue
        clean.append(n)
    return list(dict.fromkeys(clean))

# ------- 置換ユーティリティ（大小無視やNS適用に対応） -------
def _replace_text(text, remove_str, ignore_case):
    if not remove_str:
        return text
    if ignore_case:
        return re.sub(re.escape(remove_str), "", text, flags=re.IGNORECASE)
    else:
        return text.replace(remove_str, "")

# ------- 対象収集 -------
def _gather_targets(include_shapes=False, include_connected=False, include_deformers=False):
    sel = cmds.ls(selection=True, long=True) or []
    if not sel:
        cmds.warning(u"何も選択されていません。アウトライナ等でルートを選択してください。")
        return []

    desc = cmds.listRelatives(sel, allDescendents=True, fullPath=True) or []
    dag_nodes = sel + desc

    dag_filtered = []
    for n in dag_nodes:
        if _is_referenced(n): continue
        if cmds.objectType(n, isAType='transform') or cmds.nodeType(n) == 'joint':
            dag_filtered.append(n)
        elif include_shapes and cmds.objectType(n, isAType='shape'):
            dag_filtered.append(n)

    dg_nodes = set()
    if include_connected:
        raw_hist = []
        for root in dag_nodes:
            try:
                raw_hist.extend(cmds.listHistory(root, pruneDagObjects=False, allConnections=True) or [])
            except: pass
        hist_nodes = _to_node_names(raw_hist)
        raw_conn = cmds.listConnections(dag_nodes, s=True, d=True, c=False) or []
        conn_nodes = _to_node_names(raw_conn)

        for h in (hist_nodes + conn_nodes):
            if _is_referenced(h): continue
            if not cmds.objExists(h): continue
            if cmds.objectType(h, isAType='dagNode'):  # DAGは別で処理
                continue
            htype = cmds.nodeType(h)
            if (not include_deformers) and (htype in DEFAULT_DEFORMER_BLACKLIST): continue
            if htype in SAFETY_BLACKLIST: continue
            dg_nodes.add(h)

    dag_filtered.sort(key=lambda x: x.count("|"), reverse=True)
    return dag_filtered + sorted(dg_nodes)

# ------- リネーム -------
def _rename_node(node, remove_str, apply_ns, ignore_case):
    try:
        try:
            lock_states = cmds.lockNode(node, q=True, l=True)
            if lock_states and lock_states[0]:
                cmds.lockNode(node, l=False)
        except: pass

        if cmds.objectType(node, isAType='dagNode'):
            short = _short_dag_name(node)
            ns, base = _split_namespace(short)  # DAG短名にNSは基本ないが保険
            new_ns  = _replace_text(ns,   remove_str, ignore_case) if apply_ns else ns
            new_base= _replace_text(base, remove_str, ignore_case)
            new_short = (new_ns + ":" if new_ns else "") + new_base
            if new_base and new_short != short:
                cmds.rename(node, new_short)
                return (short, new_short)
            return None
        else:
            ns, base = _split_namespace(node)
            new_ns   = _replace_text(ns,   remove_str, ignore_case) if apply_ns else ns
            new_base = _replace_text(base, remove_str, ignore_case)
            new_full = (new_ns + ":" if new_ns else "") + new_base
            if new_base and new_full != node:
                cmds.rename(node, new_full)
                return (node, new_full)
            return None
    except Exception as e:
        return (u"{} (失敗)".format(node), u"{}".format(e))

def _bulk_remove(remove_str, include_shapes=False, include_connected=False, include_deformers=False,
                 apply_ns=False, ignore_case=False, dry_run=False):
    if not remove_str:
        cmds.warning(u"削除する文字列が空です。"); return 0, 0, []
    targets = _gather_targets(include_shapes, include_connected, include_deformers)
    if not targets: return 0, 0, []

    log, renamed = [], 0
    try:
        cmds.undoInfo(openChunk=True)
        if not dry_run:
            try:
                if not cmds.progressWindow(query=True, isProgressBar=True):
                    cmds.progressWindow(title=u"リネーム中", status=u"処理中...", isInterruptable=True, max=len(targets))
            except: pass

        for i, n in enumerate(targets, 1):
            if _is_referenced(n):
                log.append(u"(参照のためスキップ) {}".format(n))
            else:
                if dry_run:
                    disp_old = _short_dag_name(n) if cmds.objectType(n, isAType='dagNode') else n
                    ns, base = _split_namespace(disp_old)
                    new_ns   = _replace_text(ns,   remove_str, ignore_case) if apply_ns else ns
                    new_base = _replace_text(base, remove_str, ignore_case)
                    disp_new = (new_ns + ":" if new_ns else "") + new_base
                    if new_base and disp_new != disp_old:
                        log.append(u"{} -> {}".format(disp_old, disp_new))
                    else:
                        log.append(u"(変更なし) {}".format(disp_old))
                else:
                    res = _rename_node(n, remove_str, apply_ns, ignore_case)
                    if res and "失敗" not in res[0]:
                        renamed += 1
                        log.append(u"{} -> {}".format(res[0], res[1]))
                    elif res is None:
                        disp_old = _short_dag_name(n) if cmds.objectType(n, isAType='dagNode') else n
                        log.append(u"(変更なし) {}".format(disp_old))
                    else:
                        log.append(u"(失敗) {} : {}".format(res[0], res[1]))

            if not dry_run:
                try:
                    if cmds.progressWindow(query=True, isCancelled=True):
                        log.append(u"ユーザーにより中断されました。"); break
                    cmds.progressWindow(edit=True, progress=i)
                except: pass
    finally:
        if not dry_run:
            try: cmds.progressWindow(endProgress=True)
            except: pass
        cmds.undoInfo(closeChunk=True)

    return len(targets), renamed, log

# ------- プレビュー -------
def _show_preview_dialog(remove_str, include_shapes, include_connected, include_deformers, apply_ns, ignore_case):
    total, _would, log = _bulk_remove(remove_str, include_shapes, include_connected, include_deformers,
                                      apply_ns, ignore_case, dry_run=True)
    would_count = sum(1 for l in log if "->" in l)
    head = u"[プレビュー] 対象: {} 件 / 名前変更が起きる可能性: {} 件\n".format(total, would_count)
    body = u"\n".join(log) if log else u"(対象なし)"

    win = "BR_previewWin"
    if cmds.window(win, exists=True): cmds.deleteUI(win)
    cmds.window(win, title=u"プレビュー", sizeable=True, widthHeight=(820, 620))
    form = cmds.formLayout(nd=100)
    infoTxt = cmds.text(l=head, align="left")
    warnTxt = cmds.text(l=u"※ まだ改名されていません。実行するには『この内容で実行』を押してください。",
                        align="left", fn="boldLabelFont")
    sf = cmds.scrollField(editable=False, wordWrap=False, text=body)
    btn_run   = cmds.button(l=u"この内容で実行", bgc=(0.4,0.7,0.4),
                            c=lambda *_: _run_from_preview(win, remove_str, include_shapes, include_connected, include_deformers, apply_ns, ignore_case))
    btn_save  = cmds.button(l=u"ログを保存...", c=lambda *_: _save_preview_log(head + u"\n" + body))
    btn_close = cmds.button(l=u"閉じる", c=lambda *_: cmds.deleteUI(win))

    m=6
    cmds.formLayout(form, e=True,
        attachForm=[(infoTxt,'top',m),(infoTxt,'left',m),(infoTxt,'right',m),
                    (sf,'left',m),(sf,'right',m),
                    (btn_run,'left',m),(btn_close,'right',m),
                    (btn_save,'bottom',m),(btn_run,'bottom',m),(btn_close,'bottom',m)],
        attachControl=[(warnTxt,'top',2,infoTxt),(warnTxt,'left',0,infoTxt),
                       (sf,'top',m,warnTxt),(sf,'bottom',m,btn_run),
                       (btn_save,'right',m,btn_run),(btn_run,'right',m,btn_close)]
    )
    cmds.showWindow(win)

def _run_from_preview(win, remove_str, include_shapes, include_connected, include_deformers, apply_ns, ignore_case):
    total, renamed, log = _bulk_remove(remove_str, include_shapes, include_connected, include_deformers, apply_ns, ignore_case, dry_run=False)
    cmds.inViewMessage(amg=u"<hl>リネーム完了</hl>: 対象 {} / 変更 {} 件".format(total, renamed),
                       pos="midCenter", fade=True, alpha=0.9)
    print(u"[結果] 対象: {} / 変更: {}".format(total, renamed))
    for line in log: print(line)
    if cmds.window(win, exists=True): cmds.deleteUI(win)

def _save_preview_log(text):
    path = cmds.fileDialog2(fileFilter="Text (*.txt)", dialogStyle=2, caption=u"ログを保存", fileMode=0)
    if not path: return
    try:
        try:
            with open(path[0], 'w', encoding='utf-8') as f: f.write(text)
        except TypeError:
            with open(path[0], 'w') as f: f.write(text.encode('utf-8'))
        cmds.inViewMessage(amg=u"ログを保存しました: {}".format(path[0]), pos="topCenter", fade=True)
    except Exception as e:
        cmds.warning(u"ログ保存に失敗: {}".format(e))

# ------- メインUI -------
def _make_ui():
    if cmds.window(WIN, exists=True): cmds.deleteUI(WIN)
    cmds.window(WIN, title=u"名前から文字列を削除して一括リネーム", sizeable=False)
    cmds.columnLayout(adj=True, rs=6, cw=600)
    cmds.text(l=u"選択＋子孫から指定文字列を削除。接続DGノードやネームスペースも任意で対象化できます。", align="left")

    tf = cmds.textFieldGrp('BR_removeTF', label=u"削除する文字列", text="NEBULOOM_", cw2=(180, 380))
    cb_shapes      = cmds.checkBox('BR_includeShapesCB',  label=u"シェイプも対象にする（通常はOFF推奨）", v=False)
    cb_connected   = cmds.checkBox('BR_includeConnected', label=u"接続ノードも対象にする（履歴/シェーダ等）", v=False)
    cb_deformers   = cmds.checkBox('BR_includeDeformers', label=u"デフォーマ類（skinCluster等）も対象にする", v=False)
    cb_apply_ns    = cmds.checkBox('BR_applyNS',          label=u"ネームスペースにも適用（:の左側も置換）", v=True)
    cb_ignore_case = cmds.checkBox('BR_ignoreCase',       label=u"大文字小文字を無視して置換", v=True)
    cb_preview     = cmds.checkBox('BR_previewCB',        label=u"実行前にプレビューを表示", v=True)

    def _do_preview(*_):
        remove_str = cmds.textFieldGrp(tf, q=True, text=True)
        include_shapes    = cmds.checkBox(cb_shapes, q=True, v=True)
        include_connected = cmds.checkBox(cb_connected, q=True, v=True)
        include_deformers = cmds.checkBox(cb_deformers, q=True, v=True)
        apply_ns          = cmds.checkBox(cb_apply_ns, q=True, v=True)
        ignore_case       = cmds.checkBox(cb_ignore_case, q=True, v=True)
        _show_preview_dialog(remove_str, include_shapes, include_connected, include_deformers, apply_ns, ignore_case)

    def _do_run(*_):
        remove_str = cmds.textFieldGrp(tf, q=True, text=True)
        include_shapes    = cmds.checkBox(cb_shapes, q=True, v=True)
        include_connected = cmds.checkBox(cb_connected, q=True, v=True)
        include_deformers = cmds.checkBox(cb_deformers, q=True, v=True)
        apply_ns          = cmds.checkBox(cb_apply_ns, q=True, v=True)
        ignore_case       = cmds.checkBox(cb_ignore_case, q=True, v=True)
        want_preview      = cmds.checkBox(cb_preview, q=True, v=True)
        if want_preview:
            _show_preview_dialog(remove_str, include_shapes, include_connected, include_deformers, apply_ns, ignore_case); return
        total, renamed, log = _bulk_remove(remove_str, include_shapes, include_connected, include_deformers, apply_ns, ignore_case, dry_run=False)
        cmds.inViewMessage(amg=u"<hl>リネーム完了</hl>: 対象 {} / 変更 {} 件".format(total, renamed), pos="midCenter", fade=True, alpha=0.9)
        print(u"[結果] 対象: {} / 変更: {}".format(total, renamed)); [print(l) for l in log]

    def _add_shelf_button(*_):
        try: shelf = cmds.tabLayout('ShelfLayout', q=True, selectTab=True)
        except: shelf = None
        cmd = ("import maya.cmds as cmds\n"
               "try:\n"
               "    from __main__ import _make_ui\n"
               "except Exception:\n"
               "    raise RuntimeError(u'このボタンは、スクリプトを一度実行した後に追加してください。')\n"
               "_make_ui()\n")
        cmds.shelfButton(parent=shelf if shelf else "ShelfLayout",
                         label=u"RmStr+NS", annotation=u"選択＋子孫＋(接続/NS任意)一括リネーム",
                         sourceType="Python", command=cmd, image1="pythonFamily.png")
        cmds.inViewMessage(amg=u"<hl>シェルフに追加しました</hl>（RmStr+NS）", pos="topCenter", fade=True)

    cmds.rowLayout(nc=3, cw3=(170, 220, 170), adj=3)
    cmds.button(l=u"プレビュー", c=_do_preview, h=28)
    cmds.button(l=u"一括リネーム", bgc=(0.4,0.7,0.4), c=_do_run, h=28)
    cmds.button(l=u"シェルフにボタン追加", c=_add_shelf_button, h=28)
    cmds.setParent('..')

    cmds.separator(h=6, style="in")
    # cmds.text(l=u"※ 参照ノードは常にスキップ。NSを消すと衝突が起こりやすいので、必要に応じて実行前プレビュー推奨。", align="left", fn="oblique")
    cmds.showWindow(WIN)

_make_ui()