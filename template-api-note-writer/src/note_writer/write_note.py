from data_models import NoteResult, Post, PostWithContext, ProposedMisleadingNote
from note_writer.llm_util import (
    get_grok_live_search_response,
    get_grok_response,
    grok_describe_image,
)
from note_writer.misleading_tags import get_misleading_tags
# from pipline import *
import tweepy
import json
import os
import time
from datetime import datetime
import math
import time


def _get_prompt_for_note_writing(post_with_context_description: str, search_results: str):
    return f"""Below will be a post on X, and live search results from the web. \
If the post is misleading and needs a community note, \
then your response should be the proposed community note itself. \
If the post is not misleading, or does not contain any concrete fact-checkable claims, or there \
is not strong enough evidence to write a 100%-supported-by-evidence \
community note, then do not write a note, and instead respond with "NO NOTE NEEDED." or \
"NOT ENOUGH EVIDENCE TO WRITE A GOOD COMMUNITY NOTE.".

If a note is justified, then please write \
a very good community note, which is concise (tweet-length at most), interesting and clear to read, \
contains no unnecessary words, is backed by very solid evidence from sources that would be most likely \
to be found trustworthy by people on both sides of the political spectrum (citing URL(s)), and is \
written in a way that would be most likely to be found trustworthy by people on both sides of the \
political spectrum. \

The answer MUST be short, like a post on X (280 characters maximum, not counting URLs). \
The note should not include any sort of wasted characters e.g. [Source] when listing a URL. Just state the URL directly in the text. \
Each note MUST include at least one URL/link source. Nothing else counts as a source other than a URL/link. \
Each note MUST NOT use any hashtags (#). Keep a professional tone with no hashtags, emojis, etc. \

If the post does not need a community note (either because the original post is not misleading, \
or does not contain any concrete fact-checkable claims, \
then your response should simply be "NO NOTE NEEDED.".

If the post may need a community note, but you weren't able to find enough concrete evidence to \
write an ironclad community note, then your response should be \
"NOT ENOUGH EVIDENCE TO WRITE A GOOD COMMUNITY NOTE.".

If you are writing a note, don't preface it with anything like "Community Note:". Just write the note.

    {post_with_context_description}

    Live search results:
    ```
    {search_results}
    ```

    If you aren't sure whether the post is misleading and warrants a note, then err on the side of \
not writing a note (instead, say "NO NOTE NEEDED" or "NOT ENOUGH EVIDENCE TO WRITE A GOOD COMMUNITY NOTE"). \
Only write a note if you are extremely confident that the post is misleading, \
that the evidence is strong, and that the note will be found helpful by the community. \
For example, if a post is just making a prediction about the future, don't write a note \
saying that the prediction is uncertain or likely to be wrong. \
    """

def _get_prompt_for_note_writing_v1(post_with_context_description: str, search_results: str):
    return f"""X has a crowd-sourced fact-checking program, called Community Notes.\
Here, users can write ’notes’ on potentially misleading content.\
Community Notes will be shown publicly alongside the piece of content.\
Below will be a post from X and some comments.\
then your response should be the proposed community note itself. \
If the post is not misleading, or does not contain any concrete fact-checkable claims, or there \
is not strong enough evidence to write a 100%-supported-by-evidence \
community note, then do not write a note, and instead respond with "NO NOTE NEEDED." or \
"NOT ENOUGH EVIDENCE TO WRITE A GOOD COMMUNITY NOTE.".

If a note is justified, then please write \
a very good community note, which is concise (tweet-length at most), interesting and clear to read, \
contains no unnecessary words, is backed by very solid evidence from sources that would be most likely \
to be found trustworthy by people on both sides of the political spectrum (citing URL(s)), and is \
written in a way that would be most likely to be found trustworthy by people on both sides of the \
political spectrum. \

The answer MUST be short, like a post on X (280 characters maximum, not counting URLs). \
The note should not include any sort of wasted characters e.g. [Source] when listing a URL. Just state the URL directly in the text. \
Each note MUST NOT use any hashtags (#). Keep a professional tone with no hashtags, emojis, etc. \

If the post does not need a community note (either because the original post is not misleading, \
or does not contain any concrete fact-checkable claims, \
then your response should simply be "NO NOTE NEEDED.".

If the post may need a community note, but you weren't able to find enough concrete evidence to \
write an ironclad community note, then your response should be \
"NOT ENOUGH EVIDENCE TO WRITE A GOOD COMMUNITY NOTE.".

If you are writing a note, don't preface it with anything like "Community Note:". Just write the note.

    {post_with_context_description}

    comments:
    ```
    {search_results}
    ```

    If you aren't sure whether the post is misleading and warrants a note, then err on the side of \
not writing a note (instead, say "NO NOTE NEEDED" or "NOT ENOUGH EVIDENCE TO WRITE A GOOD COMMUNITY NOTE"). \
Only write a note if you are extremely confident that the post is misleading, \
that the evidence is strong, and that the note will be found helpful by the community. \
For example, if a post is just making a prediction about the future, don't write a note \
saying that the prediction is uncertain or likely to be wrong. \
    """


def _get_post_with_context_description_for_prompt(post_with_context: PostWithContext) -> str:
    description = f"""Post text:
```
{post_with_context.post.text}
```
"""
    images_summary = _summarize_images_for_post(post_with_context.post)
    if images_summary is not None and len(images_summary) > 0:
        description += f"""Summary of images in the post:
```
{images_summary}
```
"""
    if post_with_context.quoted_post:
        description += f"""The post of interest had quoted (referenced) another post. Here is the quoted post's text:
```
{post_with_context.quoted_post.text}
```
"""
        quoted_images_summary = _summarize_images_for_post(post_with_context.quoted_post)
        if quoted_images_summary is not None and len(quoted_images_summary) > 0:
            description += f"""Summary of images in the quoted post:
```
{quoted_images_summary}
```
"""
    
    if post_with_context.in_reply_to_post:
        description += f"""The post of interest was a reply to another post. Here is the replied-to post's text:
```
{post_with_context.in_reply_to_post.text}
```
"""
        replied_to_images_summary = _summarize_images_for_post(post_with_context.in_reply_to_post)
        if replied_to_images_summary is not None and len(replied_to_images_summary) > 0:
            description += f"""Summary of images in the replied-to post:
```
{replied_to_images_summary}
```
"""

    return description


def _get_prompt_for_live_search(post_with_context_description: str) -> str:
    return f"""Below will be a post on X. Do research on the post to determine if the post is potentially misleading. \
Your response MUST include URLs/links directly in the text, next to the claim it supports. Don't include any sort \
of wasted characters e.g. [Source] when listing a URL. Just state the URL directly in the text. \

    {post_with_context_description}
    """

def _summarize_images_for_post(post: Post) -> str:
    """
    Summarize images, if they exist. Abort if video or other unsupported media type.
    """
    images_summary = ""
    for i, media in enumerate(post.media):
        assert media.media_type == "photo" # remove assert when video support is added
        image_description = grok_describe_image(media.url)
        images_summary += f"Image {i}: {image_description}\n"
    return images_summary


def _check_for_unsupported_media(post: Post) -> bool:
    """Check if the post contains unsupported media types."""
    for media in post.media:
        if media.media_type not in []:
            return True


def _check_for_unsupported_media_in_post_with_context(post_with_context: PostWithContext) -> None:
    """Check if the post or any referenced posts contain unsupported media types."""
    if _check_for_unsupported_media(post_with_context.post):
        return True
    if post_with_context.quoted_post and _check_for_unsupported_media(post_with_context.quoted_post):
        return True
    if post_with_context.in_reply_to_post and _check_for_unsupported_media(post_with_context.in_reply_to_post):
        return True
    return False

class XPostFetcher:
    def __init__(self, bearer_token: str):
        """Initialize the Tweepy client"""
        self.client = tweepy.Client(bearer_token=bearer_token)

    def get_post(self, tweet_id: str):
        """Get tweet information for a given ID with a retry mechanism for rate limits."""
        while True:  # Use a loop to repeatedly try until successful
            try:
                response = self.client.get_tweet(
                    id=tweet_id,
                    tweet_fields=["created_at", "public_metrics", "lang", "context_annotations"],
                    expansions=["author_id"],
                    user_fields=["username", "name", "verified"]
                )
                
                if response.data:
                    tweet = response.data
                    user = response.includes["users"][0] if "users" in response.includes else None
                    return {
                        "id": tweet.id,
                        "text": tweet.text,
                        "created_at": tweet.created_at,
                        "lang": tweet.lang,
                        "public_metrics": tweet.public_metrics,
                        "author": {
                            "id": user.id if user else None,
                            "username": user.username if user else None,
                            "name": user.name if user else None,
                            "verified": user.verified if user else None,
                        } if user else None
                    }
                return None
                
            except tweepy.errors.TooManyRequests:
                print("🚨 Rate limit exceeded. Waiting for 15 minutes before retrying...")
                time.sleep(900)  # Wait for 15 minutes (900 seconds)

    def get_replies(self, tweet_id: str, limit: int = 100):
        """
        Fetch replies for a given Tweet using pagination (up to 7 days).
        自动分页，并限制最大返回数量和最大请求页数。
        
        :param tweet_id: 推文ID
        :param limit: 希望获取的最大评论数（总数，不超过）
        """
        query = f"conversation_id:{tweet_id}"
        replies = []
        seen_ids = set()

        # API 每次最多100条
        per_page = min(limit, 100)
        max_pages = math.ceil(limit / per_page)

        paginator = tweepy.Paginator(
            self.client.search_recent_tweets,
            query=query,
            tweet_fields=["created_at", "public_metrics", "lang", "author_id"],
            expansions=["author_id"],
            user_fields=["username", "name", "verified"],
            max_results=per_page,
            limit=max_pages   # 限制最大页数，节省请求次数
        )

        try:
            for response in paginator:
                if not response.data:
                    continue

                users = {u.id: u for u in response.includes.get("users", [])}

                for tweet in response.data:
                    if tweet.id in seen_ids:
                        continue
                    seen_ids.add(tweet.id)

                    user = users.get(tweet.author_id)
                    replies.append({
                        "id": tweet.id,
                        "text": tweet.text,
                        "created_at": tweet.created_at,
                        "lang": tweet.lang,
                        "public_metrics": tweet.public_metrics,
                        "author": {
                            "id": user.id if user else None,
                            "username": user.username if user else None,
                            "name": user.name if user else None,
                            "verified": user.verified if user else None,
                        } if user else None
                    })

                    if len(replies) >= limit:
                        return replies

        except tweepy.errors.TooManyRequests:
            print("Rate limit exceeded (429 Too Many Requests).")
            print("Pausing for 15 minutes before retrying...")
            time.sleep(900)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        return replies

def convert_to_timestamp(data):
    """Recursively convert datetime objects to timestamps in a dictionary or list."""
    if isinstance(data, dict):
        new_data = {}
        for key, value in data.items():
            if isinstance(value, datetime):
                new_data[key] = int(value.timestamp())
            else:
                new_data[key] = convert_to_timestamp(value)
        return new_data
    elif isinstance(data, list):
        return [convert_to_timestamp(item) for item in data]
    else:
        return data
    
# BEARER_TOKEN = r"AAAAAAAAAAAAAAAAAAAAAPYCkAEAAAAAVnWB%2FgN01ZAr%2BXwINz%2FFF67ItrM%3DQDm7LzdFpu6oFtFSZK18w0999Fo2aeHzCFGG0krrFxp8xS590c" 
BEARER_TOKEN = "" # Replace with your actual bearer token
fetcher = XPostFetcher(BEARER_TOKEN)

# def research_post_and_write_note(
#     post_with_context: PostWithContext,
# ) -> NoteResult:
#     if _check_for_unsupported_media_in_post_with_context(post_with_context):
#         return NoteResult(post=post_with_context, error="Unsupported media type (e.g. video) found in post or in referenced post.")
    
    # post_with_context_description = _get_post_with_context_description_for_prompt(post_with_context)

#     # search_prompt = _get_prompt_for_live_search(post_with_context_description)
#     # search_results = get_grok_live_search_response(search_prompt)
#     replies = fetcher.get_replies(post_with_context.post.post_id, limit=300)
#     comments = []
#     for reply in replies:
#         comment = reply["text"]
#         if predict(post_with_context.post.text, comment):
#             comments.append(comment)
#     sampled_comments = random.sample(comments, min(300, len(comments)))
#     if len(sampled_comments) < 5:
#         return NoteResult(post=post_with_context, refusal=note_or_refusal_str, context_description=post_with_context_description)
#     comments ="\n".join(sampled_comments)

#     note_prompt = _get_prompt_for_note_writing(post_with_context_description, comments)
#     note_or_refusal_str = get_grok_response(note_prompt)

#     if ("NO NOTE NEEDED" in note_or_refusal_str) or (
#         "NOT ENOUGH EVIDENCE TO WRITE A GOOD COMMUNITY NOTE" in note_or_refusal_str
#     ):
#         return NoteResult(post=post_with_context, refusal=note_or_refusal_str, context_description=post_with_context_description)

#     misleading_tags = get_misleading_tags(post_with_context_description, note_or_refusal_str)

#     return NoteResult(
#         post=post_with_context,
#         note=ProposedMisleadingNote(
#             post_id=post_with_context.post.post_id,
#             note_text=note_or_refusal_str,
#             misleading_tags=misleading_tags,
#         ),
#         context_description=post_with_context_description,
#     )

def research_post_and_write_note(
    post_with_context: PostWithContext,
) -> NoteResult:

    return NoteResult(
        post=post_with_context.model_dump(),
        note=ProposedMisleadingNote(
            post_id=post_with_context.post.post_id,
            note_text="This is a test, please ignore or rate it as not helpful.",
            misleading_tags=["other"],
        ),
        context_description="post_with_context_description",
    )