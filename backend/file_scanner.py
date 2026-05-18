import os

def scan_data_folder(base_path="data"):
    posts = []

    if not os.path.exists(base_path):
        return posts

    for influencer in os.listdir(base_path):
        inf_path = os.path.join(base_path, influencer)

        if not os.path.isdir(inf_path):
            continue

        for platform in os.listdir(inf_path):
            post_folder = os.path.join(inf_path, platform, "posts")

            if not os.path.exists(post_folder):
                continue

            for file in os.listdir(post_folder):
                posts.append({
                    "influencer": influencer,
                    "platform": platform,
                    "path": os.path.join(post_folder, file)
                })

    return posts
