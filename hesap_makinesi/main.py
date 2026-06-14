import streamlit as st
from datetime import datetime, date

def _css():
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
section[data-testid='stAppViewContainer'],[data-testid='stMain']{font-family:'Inter',sans-serif!important;}
[data-testid='stMarkdown'] *{font-family:'Inter',sans-serif!important;}
.hm-card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:24px 28px;margin-bottom:14px;}
.hm-result-box{background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.2);border-radius:12px;padding:16px 20px;margin-top:12px;}
.hm-sep{height:1px;background:rgba(255,255,255,0.06);margin:20px 0;}
.hm-row{padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.04);}
.prim-card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:24px 28px;margin-bottom:14px;}
.prim-section-label{font-family:'Inter',sans-serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;padding:6px 12px;border-radius:6px;display:inline-block;margin-bottom:12px;}
.prim-result-wrap{background:linear-gradient(135deg,rgba(16,185,129,0.06) 0%,rgba(6,182,212,0.04) 100%);border:1px solid rgba(16,185,129,0.18);border-radius:14px;padding:22px 24px;margin-top:16px;}
.prim-metric-card{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:14px 16px;height:100%;}
.prim-metric-card.highlight{background:rgba(16,185,129,0.1);border-color:rgba(16,185,129,0.3);}
.prim-metric-card.accent{background:rgba(245,158,11,0.08);border-color:rgba(245,158,11,0.25);}
.pm-label{font-family:'Inter',sans-serif;font-size:10px;font-weight:600;color:#64748B;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:6px;line-height:1;}
.pm-val{font-family:'Inter',sans-serif;font-size:22px;font-weight:800;line-height:1.1;}
.pm-val-sm{font-family:'Inter',sans-serif;font-size:15px;font-weight:700;line-height:1.2;}
.pm-val-xs{font-family:'Inter',sans-serif;font-size:13px;font-weight:600;line-height:1.3;}
.pm-sub{font-family:'Inter',sans-serif;font-size:11px;color:#475569;margin-top:4px;}
.prim-divider{height:1px;background:rgba(255,255,255,0.06);margin:16px 0;}
.prim-row-hdr{font-family:'Inter',sans-serif;font-size:10px;font-weight:700;color:#475569;letter-spacing:1.5px;text-transform:uppercase;padding:6px 0 8px;border-bottom:1px solid rgba(255,255,255,0.07);margin-bottom:6px;}
.prim-hist-val{font-family:'Inter',sans-serif;font-size:13px;padding:8px 0;line-height:1.4;}
.prim-edit-box{background:rgba(99,102,241,0.06);border:1px solid rgba(99,102,241,0.2);border-radius:12px;padding:16px 18px;margin-top:10px;}
[data-testid='stNumberInput'] label,[data-testid='stTextInput'] label,[data-testid='stSelectbox'] label,[data-testid='stDateInput'] label{font-family:'Inter',sans-serif!important;color:#94A3B8!important;font-size:11px!important;font-weight:600!important;letter-spacing:.8px!important;text-transform:uppercase!important;}
[data-testid='stNumberInput'] input,[data-testid='stTextInput'] input{font-family:'Inter',sans-serif!important;background:rgba(255,255,255,0.05)!important;border:1px solid rgba(255,255,255,0.1)!important;color:#F1F5F9!important;border-radius:10px!important;font-size:14px!important;}
[data-testid='stNumberInput'] input:focus,[data-testid='stTextInput'] input:focus{border-color:#6366F1!important;box-shadow:0 0 0 3px rgba(99,102,241,0.12)!important;}
[data-testid='stSelectbox'] > div > div{font-family:'Inter',sans-serif!important;background:rgba(255,255,255,0.05)!important;border:1px solid rgba(255,255,255,0.1)!important;color:#F1F5F9!important;border-radius:10px!important;}
h1,h2,h3{font-family:'Inter',sans-serif!important;}
</style>
"""

def _toplam_maliyet(alis, masraf_tipi, masraf_deger):
    if masraf_tipi == '%': return alis * (1 + masraf_deger / 100)
    return alis + masraf_deger
def _marj(maliyet, satis):
    if satis <= 0: return 0.0
    return (satis - maliyet) / satis * 100
def _kar(maliyet, satis): return satis - maliyet
def _fmt(val, prefix='$', decimals=2):
    return prefix + ('{:,.2f}' if decimals == 2 else '{:,.0f}').format(val)
def _renk(kar):
    if kar > 0: return '#10B981'
    if kar < 0: return '#EF4444'
    return '#F59E0B'
def _tl(val): return '{:,.0f} TL'.format(val)
def _usd(val): return '${:,.0f}'.format(val)

def _get_supabase():
    try:
        from supabase import create_client
        url = st.secrets['supabase']['url']
        key = st.secrets['supabase'].get('service_role_key') or st.secrets['supabase'].get('key')
        return create_client(url, key)
    except Exception: return None

def prim_kaydet(kisi, donem, toplam_prim, odeme_tarihi, notlar=''):
    try:
        sb = _get_supabase()
        if not sb: return False
        sb.table('prim_gecmis').insert({'kisi':kisi,'donem':donem,'toplam_prim':float(toplam_prim),'odeme_tarihi':str(odeme_tarihi),'notlar':notlar,'olusturma_tarihi':datetime.utcnow().isoformat()}).execute()
        return True
    except Exception as e:
        st.error('Kayit hatasi: ' + str(e))
        return False

def prim_sil(row_id):
    try:
        sb = _get_supabase()
        if not sb: return False
        sb.table('prim_gecmis').delete().eq('id', row_id).execute()
        return True
    except Exception as e:
        st.error('Silme hatasi: ' + str(e))
        return False

def prim_guncelle(row_id, donem, toplam_prim, odeme_tarihi, notlar):
    try:
        sb = _get_supabase()
        if not sb: return False
        sb.table('prim_gecmis').update({'donem':donem,'toplam_prim':float(toplam_prim),'odeme_tarihi':str(odeme_tarihi),'notlar':notlar}).eq('id', row_id).execute()
        return True
    except Exception as e:
        st.error('Guncelleme hatasi: ' + str(e))
        return False

def prim_listele(kisi):
    try:
        sb = _get_supabase()
        if not sb: return []
        res = sb.table('prim_gecmis').select('*').eq('kisi', kisi).order('odeme_tarihi', desc=True).execute()
        return res.data or []
    except Exception: return []

def _gecmis_odemeler(kisi, pfx):
    gecmis = prim_listele(kisi)
    ek = pfx + '_eid'
    if ek not in st.session_state: st.session_state[ek] = None
    if not gecmis:
        st.markdown('<div style="font-family:Inter,sans-serif;color:#475569;font-size:13px;padding:16px 0;text-align:center">Henüz kayıtlı ödeme yok.</div>', unsafe_allow_html=True)
        return
    h1,h2,h3,h4,h5,h6 = st.columns([1.3,1.8,1.5,2.4,0.5,0.5])
    for col,bas in zip([h1,h2,h3,h4,h5,h6],['Dönem','Toplam Prim','Ödeme Tarihi','Not','','']):
        with col: st.markdown('<div class="prim-row-hdr">'+bas+'</div>', unsafe_allow_html=True)
    sil_id = None
    for row in gecmis:
        rid = row.get('id')
        c1,c2,c3,c4,c5,c6 = st.columns([1.3,1.8,1.5,2.4,0.5,0.5])
        with c1: st.markdown('<div class="prim-hist-val" style="color:#E2E8F0;font-weight:600">'+str(row.get('donem',''))+'</div>', unsafe_allow_html=True)
        with c2: st.markdown('<div class="prim-hist-val" style="color:#10B981;font-weight:700">'+ _tl(row.get('toplam_prim',0))+'</div>', unsafe_allow_html=True)
        with c3: st.markdown('<div class="prim-hist-val" style="color:#94A3B8">'+str(row.get('odeme_tarihi',''))+'</div>', unsafe_allow_html=True)
        with c4: st.markdown('<div class="prim-hist-val" style="color:#64748B">'+(row.get('notlar','') or '—')+'</div>', unsafe_allow_html=True)
        with c5:
            if st.button('✏️', key=pfx+'_ed_'+str(rid), help='Düzenle'):
                st.session_state[ek] = rid; st.rerun()
        with c6:
            if st.button('🗑️', key=pfx+'_dl_'+str(rid), help='Sil'): sil_id = rid
        st.markdown('<div style="height:1px;background:rgba(255,255,255,0.04)"></div>', unsafe_allow_html=True)
    if sil_id: prim_sil(sil_id); st.rerun()
    if st.session_state[ek] is not None:
        erow = next((r for r in gecmis if r.get('id')==st.session_state[ek]), None)
        if erow:
            st.markdown('<div class="prim-edit-box">', unsafe_allow_html=True)
            st.markdown('<div style="font-family:Inter,sans-serif;font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#A5B4FC;margin-bottom:12px">KAYDI DÜZENLE</div>', unsafe_allow_html=True)
            e1,e2,e3,e4 = st.columns([1.5,1.5,1.5,2])
            with e1: e_d = st.text_input('Dönem', value=erow.get('donem',''), key=pfx+'_ed')
            with e2: e_p = st.number_input('Prim (TL)', min_value=0.0, value=float(erow.get('toplam_prim',0)), step=100.0, format='%.0f', key=pfx+'_ep')
            with e3:
                try: td = date.fromisoformat(str(erow.get('odeme_tarihi', date.today())))
                except: td = date.today()
                e_t = st.date_input('Ödeme Tarihi', value=td, key=pfx+'_et')
            with e4: e_n = st.text_input('Not', value=erow.get('notlar',''), key=pfx+'_en')
            b1,b2,_ = st.columns([1,1,4])
            with b1:
                if st.button('✅ Kaydet', key=pfx+'_esv', type='primary'):
                    if prim_guncelle(st.session_state[ek], e_d, e_p, e_t, e_n):
                        st.session_state[ek] = None; st.rerun()
            with b2:
                if st.button('❌ İptal', key=pfx+'_ecl'):
                    st.session_state[ek] = None; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        else: st.session_state[ek] = None

# ─── GÖKHAN YAVUZ PRİM
def _prim_gokhan():
    st.markdown(
        '<div style="font-family:Inter,sans-serif;margin-bottom:20px">'
        '<div style="font-size:18px;font-weight:800;color:#FFFFFF;margin-bottom:4px">PRİM HESAPLAMA — GÖKHAN YAVUZ</div>'
        '<div style="font-size:12px;color:#64748B">Prim = Baz Hakediş (1,5 Maaş) + Ciro Ağırlıklı Bonus &nbsp;·&nbsp; NZXT/AGI hariç</div>'
        '</div>',
        unsafe_allow_html=True)

    st.markdown('<div class="prim-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#A5B4FC;margin-bottom:14px">TEMEL PARAMETRELER</div>', unsafe_allow_html=True)
    p1,p2,p3,p4 = st.columns(4)
    with p1: donem = st.text_input('Dönem', value='Q1 2026', key='gy_donem', placeholder='Q1 2026')
    with p2: aylik_maas = st.number_input('Aylık Maaş (TL)', min_value=0.0, value=115000.0, step=1000.0, format='%.0f', key='gy_maas')
    with p3: baz_kat = st.number_input('Baz Katı', min_value=0.0, value=1.5, step=0.1, format='%.1f', key='gy_baz_kat')
    with p4: usd_kur = st.number_input('USD/TL Kuru', min_value=1.0, value=38.0, step=0.5, format='%.2f', key='gy_usd_kur')
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="prim-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#A5B4FC;margin-bottom:14px">CİRO & HEDEFLER</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:11px;font-weight:700;color:#818CF8;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">━━ KASA</div>', unsafe_allow_html=True)
    k1,k2,k3,k4 = st.columns(4)
    with k1: kasa_hedef_pct = st.number_input('Hedef (%)', min_value=0.0, value=30.0, step=0.1, format='%.1f', key='gy_kh')
    with k2: kasa_gercek_pct = st.number_input('Gerçekleşen (%)', min_value=0.0, value=0.0, step=0.1, format='%.1f', key='gy_kg')
    with k3: kasa_ciro_usd = st.number_input('Ciro (USD)', min_value=0.0, value=0.0, step=100.0, format='%.0f', key='gy_kc')
    with k4:
        kasa_carpan = (kasa_gercek_pct / kasa_hedef_pct) if kasa_hedef_pct > 0 else 0.0
        c_renk = '#10B981' if kasa_carpan >= 1 else ('#F59E0B' if kasa_carpan >= 0.8 else '#EF4444')
        st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
        st.markdown('<div style="font-family:Inter,sans-serif;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:10px 14px"><div class="pm-label">KASA Çarpan</div><div style="font-size:20px;font-weight:800;color:'+c_renk+'">{:.2f}x</div></div>'.format(kasa_carpan), unsafe_allow_html=True)
    st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:11px;font-weight:700;color:#34D399;letter-spacing:1px;text-transform:uppercase;margin:12px 0 8px">━━ SOĞ (Soğutucu)</div>', unsafe_allow_html=True)
    s1,s2,s3,s4 = st.columns(4)
    with s1: sog_hedef_pct = st.number_input('Hedef (%)', min_value=0.0, value=35.0, step=0.1, format='%.1f', key='gy_sh')
    with s2: sog_gercek_pct = st.number_input('Gerçekleşen (%)', min_value=0.0, value=0.0, step=0.1, format='%.1f', key='gy_sg')
    with s3: sog_ciro_usd = st.number_input('Ciro (USD)', min_value=0.0, value=0.0, step=100.0, format='%.0f', key='gy_sc')
    with s4:
        sog_carpan = (sog_gercek_pct / sog_hedef_pct) if sog_hedef_pct > 0 else 0.0
        s_renk = '#10B981' if sog_carpan >= 1 else ('#F59E0B' if sog_carpan >= 0.8 else '#EF4444')
        st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
        st.markdown('<div style="font-family:Inter,sans-serif;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:10px 14px"><div class="pm-label">SOĞ Çarpan</div><div style="font-size:20px;font-weight:800;color:'+s_renk+'">{:.2f}x</div></div>'.format(sog_carpan), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ─ Hesaplama: ciro tutarına göre ağırlık (DÜZELTİLDİ)
    kasa_ciro_tl = kasa_ciro_usd * usd_kur
    sog_ciro_tl = sog_ciro_usd * usd_kur
    toplam_ciro_usd = kasa_ciro_usd + sog_ciro_usd
    toplam_ciro_tl = toplam_ciro_usd * usd_kur
    baz_hakdis = baz_kat * aylik_maas
    # Ciro payları gerçek tutara göre (Excel ile aynı)
    kp = (kasa_ciro_usd / toplam_ciro_usd) if toplam_ciro_usd > 0 else 0.5
    sp = (sog_ciro_usd / toplam_ciro_usd) if toplam_ciro_usd > 0 else 0.5
    # Ağırlıklı çarpan = Σ(çarpan × ciro_payı)
    agirlikli_carpan = (kasa_carpan * kp) + (sog_carpan * sp)
    # Ciro bonus = (ağırlıklı çarpan - 1) × baz hakediş
    ciro_bonus = max(0.0, agirlikli_carpan - 1.0) * baz_hakdis
    toplam_prim = baz_hakdis + ciro_bonus
    kp_pct = kp * 100
    sp_pct = sp * 100

    # ─ Sonuç kutusu
    st.markdown('<div class="prim-result-wrap">', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#6EE7B7;margin-bottom:18px">HESAPLAMA SONUCU</div>', unsafe_allow_html=True)
    m1,m2,m3,m4,m5 = st.columns(5)
    def mcard(col, label, val, color, big=False, cls=''):
        fs = '24' if big else '16'
        fw = '800' if big else '700'
        cls_str = ' ' + cls if cls else ''
        with col:
            st.markdown('<div class="prim-metric-card'+cls_str+'"><div class="pm-label">'+label+'</div><div style="font-family:Inter,sans-serif;font-size:'+fs+'px;font-weight:'+fw+';color:'+color+'">'+val+'</div></div>', unsafe_allow_html=True)
    mcard(m1, 'Baz Hakediş (1,5 Maaş)', _tl(baz_hakdis), '#A5B4FC')
    mcard(m2, 'KASA Çarpan', '{:.2f}x'.format(kasa_carpan), '#FCD34D')
    mcard(m3, 'SOĞ Çarpan', '{:.2f}x'.format(sog_carpan), '#6EE7B7')
    mcard(m4, 'Ciro Ağ. Bonus', _tl(ciro_bonus), '#F59E0B', cls='accent')
    mcard(m5, 'TOPLAM PRİM', _tl(toplam_prim), '#10B981', big=True, cls='highlight')
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    d1,d2,d3,d4,d5 = st.columns(5)
    def dcard(col, label, val, sub='', color='#CBD5E1'):
        with col:
            sub_html = ('<div class="pm-sub">'+sub+'</div>') if sub else ''
            st.markdown('<div class="prim-metric-card"><div class="pm-label">'+label+'</div><div class="pm-val-sm" style="color:'+color+'">'+val+'</div>'+sub_html+'</div>', unsafe_allow_html=True)
    dcard(d1, 'Toplam Ciro', _usd(toplam_ciro_usd), '≈ '+_tl(toplam_ciro_tl))
    dcard(d2, 'KASA Ciro', _usd(kasa_ciro_usd), _tl(kasa_ciro_tl), '#A5B4FC')
    dcard(d3, 'KASA Pay', '%{:.1f}'.format(kp_pct), '', '#A5B4FC')
    dcard(d4, 'SOĞ Ciro', _usd(sog_ciro_usd), _tl(sog_ciro_tl), '#6EE7B7')
    dcard(d5, 'SOĞ Pay', '%{:.1f}'.format(sp_pct), '', '#6EE7B7')
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="prim-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#94A3B8;margin-bottom:12px">PRİM ÖDEMESİ KAYDET</div>', unsafe_allow_html=True)
    op1,op2,op3 = st.columns([1.5,1.5,1])
    with op1: gy_odt = st.date_input('Ödeme Tarihi', value=date.today(), key='gy_odt')
    with op2: gy_not = st.text_input('Not (opsiyonel)', placeholder='Örn: Q1 ödemesi', key='gy_not')
    with op3:
        st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
        if st.button('💾 Ödemeyi Kaydet', key='gy_save', type='primary', use_container_width=True):
            if toplam_prim > 0 and donem:
                if prim_kaydet('gokhan_yavuz', donem, toplam_prim, gy_odt, gy_not):
                    st.success('✅ '+donem+' dönemi '+_tl(toplam_prim)+' prim ödemesi kaydedildi.')
                    st.rerun()
                else: st.error('Kayıt sırasında hata oluştu.')
            else: st.warning('Dönem adı ve prim tutarı girilmeli.')
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="prim-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#94A3B8;margin-bottom:14px">GEÇMİŞ PRİM ÖDEME LERİ</div>', unsafe_allow_html=True)
    _gecmis_odemeler('gokhan_yavuz', 'gy')
    st.markdown('</div>', unsafe_allow_html=True)

# ─── AYHAN EROĞLU PRİM
def _prim_ayhan():
    st.markdown(
        '<div style="font-family:Inter,sans-serif;margin-bottom:20px">'
        '<div style="font-size:18px;font-weight:800;color:#FFFFFF;margin-bottom:4px">PRİM HESAPLAMA — AYHAN EROĞLU</div>'
        '<div style="font-size:12px;color:#64748B">Prim = Satılan adet × adet başı USD prim × USD/TL kuru</div>'
        '</div>',
        unsafe_allow_html=True)

    # Birim primler - 5 esit sutun, label kisaltildi
    st.markdown('<div class="prim-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#A5B4FC;margin-bottom:14px">BİRİM PRİM ORANLARI & KUR</div>', unsafe_allow_html=True)
    b1,b2,b3,b4,b5 = st.columns(5)
    with b1: mon_b = st.number_input('Monitör ($/adet)', min_value=0.0, value=0.50, step=0.01, format='%.2f', key='ay_mb')
    with b2: kasa_b = st.number_input('Kasa ($/adet)', min_value=0.0, value=0.50, step=0.01, format='%.2f', key='ay_kb')
    with b3: ek_b = st.number_input('E.Kartı ($/adet)', min_value=0.0, value=1.00, step=0.01, format='%.2f', key='ay_ek')
    with b4: ssd_b = st.number_input('SSD&RAM ($/adet)', min_value=0.0, value=0.50, step=0.01, format='%.2f', key='ay_sb')
    with b5: kur = st.number_input('USD/TL Kuru', min_value=1.0, value=38.0, step=0.5, format='%.2f', key='ay_kur')
    st.markdown('</div>', unsafe_allow_html=True)

    # Satis adetleri - 5 esit sutun
    st.markdown('<div class="prim-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#A5B4FC;margin-bottom:14px">SATIŞ ADETLERİ</div>', unsafe_allow_html=True)
    a1,a2,a3,a4,a5 = st.columns(5)
    with a1: ay_d = st.text_input('Dönem', value='Q1 2026', key='ay_d')
    with a2: mon_a = st.number_input('Monitör Adet', min_value=0, value=0, step=1, key='ay_ma')
    with a3: kas_a = st.number_input('Kasa Adet', min_value=0, value=0, step=1, key='ay_ka')
    with a4: ek_a = st.number_input('E.Kartı Adet', min_value=0, value=0, step=1, key='ay_ea')
    with a5: ss_a = st.number_input('SSD&RAM Adet', min_value=0, value=0, step=1, key='ay_sa')
    st.markdown('</div>', unsafe_allow_html=True)

    mon_usd = mon_a * mon_b
    kas_usd = kas_a * kasa_b
    ek_usd = ek_a * ek_b
    ssd_usd = ss_a * ssd_b
    tot_usd = mon_usd + kas_usd + ek_usd + ssd_usd
    tot_tl = tot_usd * kur

    # Sonuc - 6 kart, esit genislik, hepsi ayni satirda
    st.markdown('<div class="prim-result-wrap">', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#6EE7B7;margin-bottom:18px">HESAPLAMA SONUCU</div>', unsafe_allow_html=True)
    r1,r2,r3,r4,r5,r6 = st.columns([1,1,1,1,1.2,1.2])
    def mcard2(col, lbl, val, color, big=False):
        fs = '20' if big else '14'
        fw = '800' if big else '700'
        with col:
            st.markdown('<div class="prim-metric-card'+(' highlight' if big else '')+'" style="min-height:72px"><div class="pm-label">'+lbl+'</div><div style="font-family:Inter,sans-serif;font-size:'+fs+'px;font-weight:'+fw+';color:'+color+';line-height:1.2">'+val+'</div></div>', unsafe_allow_html=True)
    mcard2(r1, 'Monitör Prim', '${:.2f}'.format(mon_usd), '#CBD5E1')
    mcard2(r2, 'Kasa Prim', '${:.2f}'.format(kas_usd), '#CBD5E1')
    mcard2(r3, 'E.Kartı Prim', '${:.2f}'.format(ek_usd), '#CBD5E1')
    mcard2(r4, 'SSD&RAM Prim', '${:.2f}'.format(ssd_usd), '#CBD5E1')
    mcard2(r5, 'TOPLAM ($)', '${:,.2f}'.format(tot_usd), '#FCD34D', big=True)
    mcard2(r6, 'TOPLAM (TL)', _tl(tot_tl), '#10B981', big=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="prim-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#94A3B8;margin-bottom:12px">PRİM ÖDEMESİ KAYDET</div>', unsafe_allow_html=True)
    op1,op2,op3 = st.columns([1.5,1.5,1])
    with op1: ay_odt = st.date_input('Ödeme Tarihi', value=date.today(), key='ay_odt')
    with op2: ay_not = st.text_input('Not (opsiyonel)', placeholder='Örn: Q1 ödemesi', key='ay_not')
    with op3:
        st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
        if st.button('💾 Ödemeyi Kaydet', key='ay_save', type='primary', use_container_width=True):
            if tot_tl > 0 and ay_d:
                if prim_kaydet('ayhan_eroglu', ay_d, tot_tl, ay_odt, ay_not):
                    st.success('✅ '+ay_d+' dönemi '+_tl(tot_tl)+' prim ödemesi kaydedildi.')
                    st.rerun()
                else: st.error('Kayıt sırasında hata oluştu.')
            else: st.warning('Dönem adı ve prim tutarı girilmeli.')
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="prim-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#94A3B8;margin-bottom:14px">GEÇMİŞ PRİM ÖDEMELERİ</div>', unsafe_allow_html=True)
    _gecmis_odemeler('ayhan_eroglu', 'ay')
    st.markdown('</div>', unsafe_allow_html=True)

# ─── SEKME 1: ÜRÜN KARLILIK
def _urun_karlilik():
    st.markdown('<div class="hm-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#A5B4FC;margin-bottom:16px">ÜRÜN KARLILIK HESAPLAYICI</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:14px;font-weight:700;color:#FFFFFF;margin-bottom:14px">Hızlı Hesap</div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1.5,1,1])
    with c1: urun_adi = st.text_input('Ürün Adı (opsiyonel)', placeholder='Örn: Monitor XG27', key='uk_ad')
    with c2: alis = st.number_input('Alış Fiyatı ($)', min_value=0.0, value=0.0, step=0.01, format='%.2f', key='uk_alis')
    with c3: masraf_tipi = st.selectbox('Ek Masraf Tipi', ['%','$'], key='uk_masraf_tipi')
    c4,c5,c6 = st.columns([1.5,1,1])
    with c4:
        ml = 'Ek Masraf (%)' if masraf_tipi=='%' else 'Ek Masraf ($)'
        masraf_deger = st.number_input(ml, min_value=0.0, value=0.0, step=(0.1 if masraf_tipi=='%' else 0.01), format=('%.1f' if masraf_tipi=='%' else '%.2f'), key='uk_masraf')
    with c5: satis = st.number_input('Satış Fiyatı ($)', min_value=0.0, value=0.0, step=0.01, format='%.2f', key='uk_satis')
    with c6: indirim = st.number_input('İndirim ($)', min_value=0.0, value=0.0, step=0.01, format='%.2f', key='uk_indirim')
    if alis > 0 and satis > 0:
        maliyet = _toplam_maliyet(alis, masraf_tipi, masraf_deger)
        kar_n = _kar(maliyet, satis)
        marj_n = _marj(maliyet, satis)
        renk = _renk(kar_n)
        ind_s = satis - indirim if indirim > 0 else None
        if ind_s is not None and ind_s > 0:
            kar_i = _kar(maliyet, ind_s)
            renk_i = _renk(kar_i)
        st.markdown('<div class="hm-result-box">', unsafe_allow_html=True)
        st.markdown('<div style="font-family:Inter,sans-serif;color:#94A3B8;font-size:11px;font-weight:600;margin-bottom:12px">'+(urun_adi+' — ' if urun_adi else '')+'Toplam Maliyet: '+_fmt(maliyet)+'</div>', unsafe_allow_html=True)
        if ind_s and ind_s > 0:
            r1,r2,r3,r4,r5 = st.columns(5)
            data = [('Satış Fiyatı','$'+'{:,.2f}'.format(satis),'#FFFFFF'),('Kar ($)','$'+'{:,.2f}'.format(kar_n),renk),('Marj (%)','%'+'{:.1f}'.format(marj_n),renk),('İnd. Fiyat','$'+'{:,.2f}'.format(ind_s),'#F59E0B'),('İnd. Kar ($)','$'+'{:,.2f}'.format(kar_i),renk_i)]
            for col,(lbl,val,clr) in zip([r1,r2,r3,r4,r5],data):
                with col: st.markdown('<div style="font-family:Inter,sans-serif"><div class="pm-label">'+lbl+'</div><div style="font-size:22px;font-weight:800;color:'+clr+'">'+val+'</div></div>', unsafe_allow_html=True)
        else:
            r1,r2,r3 = st.columns(3)
            data = [('Satış Fiyatı','$'+'{:,.2f}'.format(satis),'#FFFFFF'),('Kar ($)','$'+'{:,.2f}'.format(kar_n),renk),('Marj (%)','%'+'{:.1f}'.format(marj_n),renk)]
            for col,(lbl,val,clr) in zip([r1,r2,r3],data):
                with col: st.markdown('<div style="font-family:Inter,sans-serif"><div class="pm-label">'+lbl+'</div><div style="font-size:26px;font-weight:800;color:'+clr+'">'+val+'</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-family:Inter,sans-serif;color:#475569;font-size:13px;padding:16px 0">Alış ve satış fiyatını girerek sonucu görün.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="hm-sep"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:14px;font-weight:700;color:#FFFFFF;margin-bottom:6px">Toplu Karşılaştırma</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;color:#64748B;font-size:12px;margin-bottom:14px">Birden fazla ürünü yan yana ekleyip karşılaştır.</div>', unsafe_allow_html=True)
    if 'uk_liste' not in st.session_state: st.session_state.uk_liste = []
    if 'uk_sayac' not in st.session_state: st.session_state.uk_sayac = 0
    with st.expander('+ Ürün Ekle', expanded=(len(st.session_state.uk_liste)==0)):
        fa1,fa2,fa3 = st.columns([2,1,1])
        with fa1: fa_ad = st.text_input('Ürün Adı', placeholder='Ürün adı veya kodu', key='fa_ad')
        with fa2: fa_alis = st.number_input('Alış ($)', min_value=0.0, value=0.0, step=0.01, format='%.2f', key='fa_alis')
        with fa3: fa_mt = st.selectbox('Masraf Tipi', ['%','$'], key='fa_masraf_tipi')
        fb1,fb2,fb3 = st.columns([2,1,1])
        with fb1:
            fa_ml = 'Ek Masraf (%)' if fa_mt=='%' else 'Ek Masraf ($)'
            fa_m = st.number_input(fa_ml, min_value=0.0, value=0.0, step=(0.1 if fa_mt=='%' else 0.01), format=('%.1f' if fa_mt=='%' else '%.2f'), key='fa_masraf')
        with fb2: fa_s = st.number_input('Satış ($)', min_value=0.0, value=0.0, step=0.01, format='%.2f', key='fa_satis')
        with fb3: fa_i = st.number_input('İndirim ($)', min_value=0.0, value=0.0, step=0.01, format='%.2f', key='fa_indirim')
        if st.button('Listeye Ekle', key='fa_ekle', type='primary'):
            if fa_alis > 0 and fa_s > 0:
                st.session_state.uk_sayac += 1
                me = _toplam_maliyet(fa_alis, fa_mt, fa_m)
                ke = _kar(me, fa_s); mre = _marj(me, fa_s)
                is2 = fa_s - fa_i if fa_i > 0 else None
                kie = _kar(me, is2) if is2 and is2>0 else None
                mie = _marj(me, is2) if is2 and is2>0 else None
                st.session_state.uk_liste.append({'id':st.session_state.uk_sayac,'ad':fa_ad or ('Ürün '+str(st.session_state.uk_sayac)),'alis':fa_alis,'masraf_tipi':fa_mt,'masraf':fa_m,'maliyet':me,'satis':fa_s,'indirim':fa_i,'kar':ke,'marj':mre,'ind_satis':is2,'kar_ind':kie,'marj_ind':mie})
                st.rerun()
            else: st.warning('Alış ve satış fiyatı girilmeli.')
    if st.session_state.uk_liste:
        h1,h2,h3,h4,h5,h6,h7,h8 = st.columns([2,1.2,1.2,1.2,1.2,1.2,1.2,0.6])
        for col,bas in zip([h1,h2,h3,h4,h5,h6,h7,h8],['Ürün','Alış ($)','Maliyet ($)','Satış ($)','Kar ($)','Marj (%)','İnd. Kar ($)','']):
            with col: st.markdown('<div class="pm-label">'+bas+'</div>', unsafe_allow_html=True)
        silinecek = None
        for u in st.session_state.uk_liste:
            ru = _renk(u['kar'])
            u1,u2,u3,u4,u5,u6,u7,u8 = st.columns([2,1.2,1.2,1.2,1.2,1.2,1.2,0.6])
            with u1: st.markdown('<div style="font-family:Inter,sans-serif;color:#E2E8F0;font-size:13px;padding:8px 0">'+u['ad']+'</div>', unsafe_allow_html=True)
            with u2: st.markdown('<div style="font-family:Inter,sans-serif;color:#CBD5E1;font-size:13px;padding:8px 0">$'+'{:,.2f}'.format(u['alis'])+'</div>', unsafe_allow_html=True)
            with u3: st.markdown('<div style="font-family:Inter,sans-serif;color:#94A3B8;font-size:13px;padding:8px 0">$'+'{:,.2f}'.format(u['maliyet'])+'</div>', unsafe_allow_html=True)
            with u4: st.markdown('<div style="font-family:Inter,sans-serif;color:#CBD5E1;font-size:13px;padding:8px 0">$'+'{:,.2f}'.format(u['satis'])+'</div>', unsafe_allow_html=True)
            with u5: st.markdown('<div style="font-family:Inter,sans-serif;color:'+ru+';font-size:13px;font-weight:700;padding:8px 0">$'+'{:,.2f}'.format(u['kar'])+'</div>', unsafe_allow_html=True)
            with u6: st.markdown('<div style="font-family:Inter,sans-serif;color:'+ru+';font-size:13px;font-weight:700;padding:8px 0">%'+'{:.1f}'.format(u['marj'])+'</div>', unsafe_allow_html=True)
            with u7:
                if u['kar_ind'] is not None:
                    ri = _renk(u['kar_ind'])
                    st.markdown('<div style="font-family:Inter,sans-serif;color:'+ri+';font-size:13px;padding:8px 0">$'+'{:,.2f}'.format(u['kar_ind'])+'</div>', unsafe_allow_html=True)
                else: st.markdown('<div style="color:#475569;font-size:12px;padding:8px 0">—</div>', unsafe_allow_html=True)
            with u8:
                if st.button('✕', key='uk_sil_'+str(u['id']), help='Sil'): silinecek = u['id']
            st.markdown('<div style="height:1px;background:rgba(255,255,255,0.04)"></div>', unsafe_allow_html=True)
        if silinecek: st.session_state.uk_liste=[x for x in st.session_state.uk_liste if x['id']!=silinecek]; st.rerun()
        if st.button('Listeyi Temizle', key='uk_temizle'): st.session_state.uk_liste=[]; st.rerun()
    else: st.markdown('<div style="font-family:Inter,sans-serif;color:#475569;font-size:13px;padding:12px 0">Henüz ürün eklenmedi.</div>', unsafe_allow_html=True)

# ─── SEKME 2: BREAK-EVEN
def _breakeven():
    st.markdown('<div class="hm-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#FCD34D;margin-bottom:16px">KIRILMA NOKTASI HESAPLAYICI</div>', unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1:
        st.markdown('<div style="font-family:Inter,sans-serif;font-size:14px;font-weight:700;color:#FFFFFF;margin-bottom:14px">Parametreler</div>', unsafe_allow_html=True)
        periyot = st.selectbox('Periyot', ['Günlük','Haftalık','Aylık','Yıllık'], index=2, key='be_periyot')
        gider = st.number_input('Sabit Gider ($) — '+periyot, min_value=0.0, value=0.0, step=10.0, format='%.2f', key='be_gider')
        marj = st.number_input('Ortalama Marj (%)', min_value=0.1, max_value=99.9, value=30.0, step=0.1, format='%.1f', key='be_marj')
        ort_fiyat = st.number_input('Ortalama Ürün Fiyatı ($)', min_value=0.0, value=0.0, step=1.0, format='%.2f', key='be_ort_fiyat')
        mevcut = st.number_input('Mevcut Ciro ($) — '+periyot, min_value=0.0, value=0.0, step=100.0, format='%.2f', key='be_mevcut')
    with c2:
        st.markdown('<div style="font-family:Inter,sans-serif;font-size:14px;font-weight:700;color:#FFFFFF;margin-bottom:14px">Sonuç</div>', unsafe_allow_html=True)
        if gider > 0 and marj > 0:
            hedef = gider / (marj / 100)
            kalan = max(0.0, hedef - mevcut)
            pct = min(1.0, mevcut / hedef) * 100 if hedef > 0 else 0.0
            asindi = mevcut >= hedef
            bar_renk = '#10B981' if asindi else '#6366F1'
            st.markdown('<div class="pm-label">Hedef Ciro ('+periyot+')</div><div style="font-family:Inter,sans-serif;font-size:26px;font-weight:800;color:#A5B4FC">$'+'{:,.0f}'.format(hedef)+'</div>', unsafe_allow_html=True)
            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
            st.markdown('<div class="pm-label">İlerleme — %'+'{:.1f}'.format(pct)+'</div><div style="height:10px;background:rgba(255,255,255,0.08);border-radius:5px;overflow:hidden;margin:6px 0"><div style="height:100%;width:'+'{:.1f}'.format(pct)+'%;background:'+bar_renk+';border-radius:5px"></div></div>', unsafe_allow_html=True)
            st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
            if asindi:
                fazla = mevcut - hedef
                st.markdown('<div style="font-family:Inter,sans-serif;font-size:18px;font-weight:700;color:#10B981">Hedef Aşıldı &nbsp;<span style="font-size:13px;color:#6EE7B7">+$'+'{:,.0f}'.format(fazla)+' fazla</span></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="pm-label">Kalan Ciro</div><div style="font-family:Inter,sans-serif;font-size:20px;font-weight:700;color:#F59E0B">$'+'{:,.0f}'.format(kalan)+'</div>', unsafe_allow_html=True)
            if ort_fiyat > 0:
                st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
                st.markdown('<div class="pm-label">Hedef / Kalan Adet</div><div style="font-family:Inter,sans-serif;font-size:16px;font-weight:700;color:#C4B5FD">'+'{:,.0f}'.format(hedef/ort_fiyat)+' &nbsp;<span style="color:#64748B;font-size:13px">/ '+'{:,.0f}'.format(kalan/ort_fiyat)+' kalan</span></div>', unsafe_allow_html=True)
            gun_map={'Günlük':1,'Haftalık':7,'Aylık':30,'Yıllık':365}
            if kalan > 0:
                gd = kalan / gun_map.get(periyot,30)
                st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
                st.markdown('<div class="pm-label">Hedefe Ulaşmak İçin</div><div style="font-family:Inter,sans-serif;font-size:16px;font-weight:700;color:#FCD34D">$'+'{:,.0f}'.format(gd)+'/gün</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-family:Inter,sans-serif;color:#475569;font-size:13px;padding:20px 0">Gider ve marj girerek kırılma noktasını hesaplayın.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ─── RUN
def run():
    st.markdown(_css(), unsafe_allow_html=True)
    st.markdown('<div style="font-family:Inter,sans-serif;margin-bottom:28px"><div style="display:inline-block;padding:4px 14px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.25);border-radius:20px;margin-bottom:10px"><span style="font-size:10px;font-weight:700;color:#FCD34D;letter-spacing:1.5px;text-transform:uppercase">Hesap Makinesi</span></div><h1 style="font-size:clamp(22px,4vw,32px);font-weight:800;color:#FFFFFF;margin:0;line-height:1.1">Hesap Makinesi</h1><p style="color:#64748B;font-size:13px;margin-top:6px">Ürün karlılık analizi, kırılma noktası ve prim hesaplama</p></div>', unsafe_allow_html=True)
    if 'hm_sekme' not in st.session_state: st.session_state.hm_sekme = 'karlilik'
    t1,t2,t3,t4,_ = st.columns([1.4,1.4,1.4,1.4,4])
    with t1:
        if st.button('Ürün Karlılık', key='tab_k', type=('primary' if st.session_state.hm_sekme=='karlilik' else 'secondary'), use_container_width=True):
            st.session_state.hm_sekme='karlilik'; st.rerun()
    with t2:
        if st.button('Kırılma Noktası', key='tab_b', type=('primary' if st.session_state.hm_sekme=='breakeven' else 'secondary'), use_container_width=True):
            st.session_state.hm_sekme='breakeven'; st.rerun()
    with t3:
        if st.button('💰 Gökhan Prim', key='tab_gy', type=('primary' if st.session_state.hm_sekme=='prim_gokhan' else 'secondary'), use_container_width=True):
            st.session_state.hm_sekme='prim_gokhan'; st.rerun()
    with t4:
        if st.button('💰 Ayhan Prim', key='tab_ay', type=('primary' if st.session_state.hm_sekme=='prim_ayhan' else 'secondary'), use_container_width=True):
            st.session_state.hm_sekme='prim_ayhan'; st.rerun()
    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
    if st.session_state.hm_sekme == 'karlilik': _urun_karlilik()
    elif st.session_state.hm_sekme == 'breakeven': _breakeven()
    elif st.session_state.hm_sekme == 'prim_gokhan': _prim_gokhan()
    elif st.session_state.hm_sekme == 'prim_ayhan': _prim_ayhan()
