"""Copy V3 canvas images into the app bundle under readable names, sized for @3x.

Source: blobs downloaded from the V3 canvas (Artifact read with path = blob id,
see docs/onboarding-v3-progress.md). Usage:

    python3 scripts/v3_assets.py <blobs_dir>

Writes mobile/assets/v3/onb/*. Icons are shown at ≤56 pt, so 168 px is @3x;
mascots up to 196 pt keep their 480 px source; photos are re-encoded JPEG.
Demo people (social-proof photos) are deliberately not copied: they never ship.
"""
import os
import sys

from PIL import Image

OUT = os.path.join(os.path.dirname(__file__), '..', 'assets', 'v3', 'onb')

# name: (blob id prefix, max px or None to keep, kind)
ASSETS = {
    # sticker icons (style C, palette P2)
    'goal_lose': ('179b7545', 168, 'png'),       # misc_tape
    'goal_maintain': ('c489f648', 168, 'png'),   # acc_apple
    'goal_gain': ('18fc2b48', 168, 'png'),       # misc_dumbbell
    'goal_track': ('d3281d47', 168, 'png'),      # feat_snap
    'src_podcast': ('ed39ea14', 168, 'png'),
    'src_tv': ('1c315a7b', 168, 'png'),
    'src_doctor': ('b2f7070d', 168, 'png'),
    'src_friends': ('384adff2', 168, 'png'),
    'misc_dots': ('24e98943', 168, 'png'),
    'act_armchair': ('43e36eae', 168, 'png'),
    'act_sneaker': ('644b260e', 168, 'png'),
    'act_bike': ('dbf6dc12', 168, 'png'),
    'act_kettlebell': ('7463163e', 168, 'png'),
    'pace_tortoise': ('0416fbd8', 168, 'png'),
    'pace_rabbit': ('00bb49b1', 168, 'png'),
    'pace_cheetah': ('a4f1daca', 168, 'png'),
    'misc_notebook': ('517bc897', 168, 'png'),
    'bar_sprout': ('e1f5a115', 168, 'png'),
    'bar_time': ('ec375e18', 168, 'png'),
    'bar_dice': ('f0a12bd5', 168, 'png'),
    'bar_battery': ('2820c07e', 168, 'png'),
    'bar_takeaway': ('3a8ae84f', 168, 'png'),
    'acc_flame': ('06713a43', 168, 'png'),
    'feat_snap': ('d3281d47', 168, 'png'),
    'feat_verified': ('560cf2ba', 168, 'png'),
    'feat_target': ('c08f082e', 168, 'png'),
    'app_icon': ('d8493939', 168, 'png'),
    # mascots and decorations
    'mascot_heart': ('bb20d3fb', None, 'png'),
    'mascot_great': ('6165c29f', None, 'png'),
    'mascot_stellar': ('8278c1b3', None, 'png'),
    'laurel_left': ('1251bc6e', None, 'png'),
    'laurel_right': ('5de406de', None, 'png'),
    # photos and video
    'bg_costa': ('b5edbe00', None, 'jpg'),  # 1080 px wide, shown 390 pt full-bleed
    'welcome_d_poster': ('7180eb62', None, 'png'),
    'welcome_d': ('6b625179', None, 'mp4'),
}


# Paywall 17–19 and offer 20 (assets/v3/pw). Photos are shown full-bleed
# (390 × 694 pt); the sources are 941 px wide, kept as they are.
PAYWALL = {
    'b3_joe': ('ffc539e5', None, 'jpg'),
    'b3_home': ('a6350fb7', None, 'jpg'),      # also the offer's close-up
    'b3_office': ('3db183b1', None, 'jpg'),
    'b3_wide': ('4da4cd69', None, 'jpg'),
    'offer_costa': ('2c4f463f', None, 'jpg'),
    'bell': ('602f3f97', 450, 'png'),          # 150 pt
    'phone_frame': ('854554d9', None, 'png'),
    'p1_photo': ('8d600f24', None, 'mp4'),
    'p1_photo_poster': ('002ebc33', None, 'jpg'),
    'p1_text': ('f245b2cb', None, 'mp4'),
    'p1_text_poster': ('e5824d3c', None, 'jpg'),
    'p1_voice': ('bfb10dd6', None, 'mp4'),
    'p1_voice_poster': ('b660976e', None, 'jpg'),
}
PW_OUT = os.path.join(os.path.dirname(__file__), '..', 'assets', 'v3', 'pw')


def main(blobs: str) -> None:
    files = os.listdir(blobs)
    for out, table in ((OUT, ASSETS), (PW_OUT, PAYWALL)):
        os.makedirs(out, exist_ok=True)
        copy(blobs, files, out, table)


def copy(blobs: str, files: list, out: str, table: dict) -> None:
    for name, (prefix, size, kind) in table.items():
        src = next(os.path.join(blobs, f) for f in files if f.startswith(prefix))
        dst = os.path.join(out, f'{name}.{kind}')
        if kind == 'mp4':
            with open(src, 'rb') as a, open(dst, 'wb') as b:
                b.write(a.read())
            continue
        im = Image.open(src)
        if size and max(im.size) > size:
            ratio = size / max(im.size)
            im = im.resize((round(im.size[0] * ratio), round(im.size[1] * ratio)), Image.LANCZOS)
        if kind == 'jpg':
            im.convert('RGB').save(dst, quality=84, optimize=True, progressive=True)
        else:
            im.save(dst, optimize=True)
        print(name, im.size, os.path.getsize(dst) // 1024, 'KB')


if __name__ == '__main__':
    main(sys.argv[1])
