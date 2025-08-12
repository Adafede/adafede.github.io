from get_all_posts import get_all_posts
from update_all_posts import update_all_posts


def prerender():
    post_files = get_all_posts("posts")
    update_all_posts(post_files)


if __name__ == "__main__":
    prerender()
