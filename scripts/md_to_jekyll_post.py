from os import makedirs
from os.path import basename, exists

import time

import sys

import subprocess


def add_front_matter(md_path):
    f = open(md_path, "r")
    title = f.readline().strip('\n')
    all_content = f.readlines()
    f.close()
    file_name = basename(md_path).split(".")[0]
    if not exists("../_posts/"):
        makedirs("./_posts/")
    new_file_name = "../_posts/{date}-{title}.md".format(
        date=time.strftime("%Y-%m-%d", time.localtime()),
        title=file_name)
    front_matter_date = time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime())
    if title.startswith("# "):
        new_title = title[len("# "):len(title)]
    else:
        new_title = file_name
    output = open(new_file_name, "w+")
    output.write("---\ntitle: {title}\ndate: {date}\n---\n".format(title=new_title, date=front_matter_date))
    output.writelines(all_content)
    output.close()
    return new_file_name


def main():
    if len(sys.argv) > 2:
        print("You can just input one file only")
        return
    if len(sys.argv) == 1:
        print("""
        You should append the input file name after the command, then try again.
        e.g: md_to_jekyll_post.py [file name]
        """.format())
        return

    input_file_name = sys.argv[1]

    try:
        subprocess.call(["open", "-R", add_front_matter(input_file_name)])
    except FileNotFoundError as err:
        print("{err}, please try again.".format(err=err))


if __name__ == '__main__':
    main()


